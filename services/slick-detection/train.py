"""
SIH26143 – U-Net Training Script for SAR Oil-Spill Detection
=============================================================
Dataset : Sentinel-1 SAR Oil-Spill Dataset
          Part I   → https://zenodo.org/records/8346860
          Part II  → https://zenodo.org/records/8253899
          Part III → https://zenodo.org/records/13761290

Expected folder structure after download:
  data/
    train/
      images/   ← GeoTIFF SAR patches (VV polarization, 256×256)
      masks/    ← Binary PNG/TIF masks  (0=water, 1=oil-spill)
    val/
      images/
      masks/

Usage:
  python train.py --data_dir data/ --epochs 50 --batch_size 8 --lr 1e-4
"""

import os
import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau
import rasterio
from rasterio.transform import from_bounds
import cv2
from pathlib import Path
import json
import sys

sys.path.append(os.path.dirname(__file__))
from unet_model import UNet

# ─── Reproducibility ─────────────────────────────────────────────────
torch.manual_seed(42)
np.random.seed(42)


# ─── Dataset ──────────────────────────────────────────────────────────
class SAROilSpillDataset(Dataset):
    """
    Loads SAR GeoTIFF patches and binary oil-spill masks.
    Supports VV, VH, or dual-polarization input.
    """
    def __init__(self, image_dir: str, mask_dir: str, img_size: int = 256, augment: bool = True):
        self.image_dir = Path(image_dir)
        self.mask_dir  = Path(mask_dir)
        self.img_size  = img_size
        self.augment   = augment

        self.image_files = sorted([
            f for f in self.image_dir.iterdir()
            if f.suffix.lower() in ('.tif', '.tiff', '.png')
        ])
        assert len(self.image_files) > 0, f"No images found in {image_dir}"
        print(f"  Loaded {len(self.image_files)} samples from {image_dir}")

    def __len__(self):
        return len(self.image_files)

    def _load_sar(self, path: Path) -> np.ndarray:
        """Read SAR GeoTIFF, calibrate, and normalize to [0, 1]."""
        with rasterio.open(path) as src:
            img = src.read(1).astype(np.float32)   # VV polarization

        # Clip extreme backscatter values (dB range)
        img = np.clip(img, -30, 10)
        # Min-max normalize
        img = (img + 30) / 40.0
        img = np.nan_to_num(img, nan=0.0)
        return img

    def _load_mask(self, path: Path) -> np.ndarray:
        """Read binary mask (0 = water, 1 = oil spill)."""
        if path.suffix.lower() in ('.tif', '.tiff'):
            with rasterio.open(path) as src:
                mask = src.read(1).astype(np.float32)
        else:
            mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE).astype(np.float32)
            mask = (mask > 127).astype(np.float32)
        return mask

    def _resize(self, arr: np.ndarray) -> np.ndarray:
        return cv2.resize(arr, (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST)

    def _augment(self, img: np.ndarray, mask: np.ndarray):
        """Random horizontal/vertical flip + 90° rotation."""
        if np.random.rand() > 0.5:
            img, mask = np.fliplr(img), np.fliplr(mask)
        if np.random.rand() > 0.5:
            img, mask = np.flipud(img), np.flipud(mask)
        k = np.random.choice([0, 1, 2, 3])
        img  = np.rot90(img, k)
        mask = np.rot90(mask, k)
        return np.ascontiguousarray(img), np.ascontiguousarray(mask)

    def __getitem__(self, idx):
        img_path  = self.image_files[idx]
        mask_path = self.mask_dir / img_path.name
        if not mask_path.exists():
            for ext in ('.png', '.tif', '.tiff', '.bmp'):
                candidate = self.mask_dir / (img_path.stem + ext)
                if candidate.exists():
                    mask_path = candidate
                    break

        img  = self._load_sar(img_path)
        mask = self._load_mask(mask_path)

        img  = self._resize(img)
        mask = self._resize(mask)

        if self.augment:
            img, mask = self._augment(img, mask)

        img  = torch.from_numpy(img).unsqueeze(0)    # (1, H, W)
        mask = torch.from_numpy(mask).unsqueeze(0)   # (1, H, W)
        return img, mask


# ─── Loss Functions ───────────────────────────────────────────────────
class DiceLoss(nn.Module):
    """Dice loss for imbalanced segmentation (oil spill << water)."""
    def __init__(self, smooth=1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, pred, target):
        pred   = torch.sigmoid(pred)
        pred   = pred.view(-1)
        target = target.view(-1)
        intersection = (pred * target).sum()
        return 1 - (2. * intersection + self.smooth) / (pred.sum() + target.sum() + self.smooth)


class CombinedLoss(nn.Module):
    """BCE + Dice (0.5 each) — standard for medical/remote-sensing seg."""
    def __init__(self, bce_weight=0.5):
        super().__init__()
        self.bce_weight  = bce_weight
        self.bce  = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([10.0]))  # class imbalance
        self.dice = DiceLoss()

    def forward(self, pred, target):
        return self.bce_weight * self.bce(pred, target) + (1 - self.bce_weight) * self.dice(pred, target)


# ─── Metrics ──────────────────────────────────────────────────────────
def iou_score(pred_logits: torch.Tensor, target: torch.Tensor, threshold=0.5) -> float:
    pred = (torch.sigmoid(pred_logits) > threshold).float()
    intersection = (pred * target).sum()
    union        = pred.sum() + target.sum() - intersection
    return (intersection / (union + 1e-6)).item()

def dice_score(pred_logits: torch.Tensor, target: torch.Tensor, threshold=0.5) -> float:
    pred = (torch.sigmoid(pred_logits) > threshold).float()
    intersection = (pred * target).sum()
    return (2 * intersection / (pred.sum() + target.sum() + 1e-6)).item()


# ─── Training Loop ────────────────────────────────────────────────────
def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, total_iou, total_dice = 0.0, 0.0, 0.0

    for imgs, masks in loader:
        imgs, masks = imgs.to(device), masks.to(device)
        optimizer.zero_grad()
        preds = model(imgs)
        loss  = criterion(preds, masks)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        total_iou  += iou_score(preds, masks)
        total_dice += dice_score(preds, masks)

    n = len(loader)
    return total_loss / n, total_iou / n, total_dice / n


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()
    total_loss, total_iou, total_dice = 0.0, 0.0, 0.0

    for imgs, masks in loader:
        imgs, masks = imgs.to(device), masks.to(device)
        preds = model(imgs)
        loss  = criterion(preds, masks)
        total_loss += loss.item()
        total_iou  += iou_score(preds, masks)
        total_dice += dice_score(preds, masks)

    n = len(loader)
    return total_loss / n, total_iou / n, total_dice / n


# ─── Main ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train U-Net on SAR Oil-Spill data")
    parser.add_argument('--data_dir',   type=str, default='../../data',  help='Root data directory')
    parser.add_argument('--save_dir',   type=str, default='checkpoints', help='Where to save model weights')
    parser.add_argument('--epochs',     type=int, default=50)
    parser.add_argument('--batch_size', type=int, default=8)
    parser.add_argument('--lr',         type=float, default=1e-4)
    parser.add_argument('--img_size',   type=int, default=256)
    parser.add_argument('--resume',     type=str, default=None, help='Path to checkpoint to resume from')
    args = parser.parse_args()

    # Directories
    train_img  = os.path.join(args.data_dir, 'train', 'images')
    train_mask = os.path.join(args.data_dir, 'train', 'masks')
    val_img    = os.path.join(args.data_dir, 'val',   'images')
    val_mask   = os.path.join(args.data_dir, 'val',   'masks')
    os.makedirs(args.save_dir, exist_ok=True)

    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"\n{'='*60}")
    print(f"  SIH26143 U-Net Training – Oil Spill Detection")
    print(f"  Device  : {device}")
    print(f"  Epochs  : {args.epochs}")
    print(f"  Batch   : {args.batch_size}")
    print(f"  LR      : {args.lr}")
    print(f"{'='*60}\n")

    # Datasets
    print("Loading datasets...")
    train_ds = SAROilSpillDataset(train_img, train_mask, args.img_size, augment=True)
    val_ds   = SAROilSpillDataset(val_img,   val_mask,   args.img_size, augment=False)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=args.batch_size, shuffle=False, num_workers=0)

    # Model
    model     = UNet(n_channels=1, n_classes=1).to(device)
    criterion = CombinedLoss(bce_weight=0.5).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(optimizer, mode='min', patience=5, factor=0.5)

    start_epoch = 0
    best_iou    = 0.0
    history     = []

    # Resume checkpoint
    if args.resume and os.path.exists(args.resume):
        ckpt = torch.load(args.resume, map_location=device)
        model.load_state_dict(ckpt['model_state'])
        optimizer.load_state_dict(ckpt['optimizer_state'])
        start_epoch = ckpt['epoch'] + 1
        best_iou    = ckpt.get('best_iou', 0.0)
        print(f"  ✓ Resumed from epoch {start_epoch}, best IoU: {best_iou:.4f}\n")

    # ── Training Loop ──────────────────────────────────────────────
    for epoch in range(start_epoch, args.epochs):
        tr_loss, tr_iou, tr_dice = train_one_epoch(model, train_loader, optimizer, criterion, device)
        va_loss, va_iou, va_dice = validate(model, val_loader, criterion, device)
        scheduler.step(va_loss)

        is_best = va_iou > best_iou
        if is_best:
            best_iou = va_iou

        # Save latest checkpoint
        torch.save({
            'epoch':          epoch,
            'model_state':    model.state_dict(),
            'optimizer_state': optimizer.state_dict(),
            'best_iou':       best_iou,
        }, os.path.join(args.save_dir, 'latest.pt'))

        # Save best model separately
        if is_best:
            torch.save(model.state_dict(), os.path.join(args.save_dir, 'best_model.pt'))

        # Log
        row = {
            "epoch": epoch + 1,
            "train_loss": round(tr_loss, 4), "train_iou": round(tr_iou, 4), "train_dice": round(tr_dice, 4),
            "val_loss":   round(va_loss, 4), "val_iou":   round(va_iou, 4), "val_dice":   round(va_dice, 4),
        }
        history.append(row)
        best_marker = " ← BEST" if is_best else ""

        print(f"  Epoch {epoch+1:>3}/{args.epochs} │ "
              f"Train Loss: {tr_loss:.4f}  IoU: {tr_iou:.4f}  Dice: {tr_dice:.4f} │ "
              f"Val Loss: {va_loss:.4f}  IoU: {va_iou:.4f}  Dice: {va_dice:.4f}{best_marker}")

    # Save training history
    with open(os.path.join(args.save_dir, 'history.json'), 'w') as f:
        json.dump(history, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Training complete!")
    print(f"  Best Validation IoU : {best_iou:.4f}")
    print(f"  Best weights saved  : {args.save_dir}/best_model.pt")
    print(f"  History saved       : {args.save_dir}/history.json")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
