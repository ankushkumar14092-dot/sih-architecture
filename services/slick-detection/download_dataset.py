"""
Dataset Helper – SIH26143
=========================
Sentinel-1 SAR Oil-Spill Dataset from Zenodo:
  - Part I   (Oil Spill Train/Val, ~40.7 GB) : https://zenodo.org/records/8346860
  - Part II  (Lookalike / No-Oil, ~45.9 GB) : https://zenodo.org/records/8253899
  - Part III (Test Images & Truth, ~9.8 GB) : https://zenodo.org/records/13761290

Usage:
  # Check status & generate quick sample dataset (Immediate):
  python download_dataset.py --sample

  # Download real Zenodo dataset (requires high-speed internet & 50+ GB disk):
  python download_dataset.py --download-zenodo --part 1
"""

import os
import sys
import argparse
import shutil
import urllib.request
from pathlib import Path
import numpy as np

ZENODO_FILES = {
    "1": {
        "record": "8346860",
        "description": "Part I: Oil Spill Training & Validation Images (1200 SAR pairs)",
        "files": [
            {
                "name": "01_Train_Val_Oil_Spill_images.7z",
                "size_gb": 40.7,
                "url": "https://zenodo.org/api/records/8346860/files/01_Train_Val_Oil_Spill_images.7z/content"
            },
            {
                "name": "01_Train_Val_Oil_Spill_mask.7z",
                "size_gb": 0.006,
                "url": "https://zenodo.org/api/records/8346860/files/01_Train_Val_Oil_Spill_mask.7z/content"
            }
        ]
    },
    "2": {
        "record": "8253899",
        "description": "Part II: Lookalike & No-Oil Images",
        "files": [
            {
                "name": "01_Train_Val_Lookalike_images.7z",
                "size_gb": 22.9,
                "url": "https://zenodo.org/api/records/8253899/files/01_Train_Val_Lookalike_images.7z/content"
            },
            {
                "name": "01_Train_Val_No_Oil_Images.7z",
                "size_gb": 22.9,
                "url": "https://zenodo.org/api/records/8253899/files/01_Train_Val_No_Oil_Images.7z/content"
            }
        ]
    },
    "3": {
        "record": "13761290",
        "description": "Part III: Test Set & Ground Truth",
        "files": [
            {
                "name": "02_Test_images_and_ground_truth.7z",
                "size_gb": 9.8,
                "url": "https://zenodo.org/api/records/13761290/files/02_Test_images_and_ground_truth.7z/content"
            }
        ]
    }
}

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR  = ROOT_DIR / "data" / "raw"
DATA_DIR = ROOT_DIR / "data"

def download_with_progress(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  ✓ File already exists: {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"  ↓ Downloading {dest.name} from Zenodo...")
    print(f"    URL: {url}")
    
    def reporthook(blocknum, blocksize, totalsize):
        read = blocknum * blocksize
        if totalsize > 0:
            percent = min(100.0, read * 100.0 / totalsize)
            sys.stdout.write(f"\r    Progress: {percent:.1f}% ({read/1e6:.1f} / {totalsize/1e6:.1f} MB)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=reporthook)
    print("\n  ✓ Download complete!")

def create_sample_dataset():
    """Generates ready-to-train sample patches so users can test immediately."""
    import rasterio
    from rasterio.transform import from_bounds
    import cv2

    print("\n📦 Generating realistic Sentinel-1 SAR training/val sample dataset...")
    train_img_dir = DATA_DIR / "train" / "images"
    train_mask_dir = DATA_DIR / "train" / "masks"
    val_img_dir = DATA_DIR / "val" / "images"
    val_mask_dir = DATA_DIR / "val" / "masks"

    for d in [train_img_dir, train_mask_dir, val_img_dir, val_mask_dir]:
        d.mkdir(parents=True, exist_ok=True)

    np.random.seed(42)
    # Generate 16 sample SAR patches (256x256)
    for i in range(16):
        is_val = (i >= 12)
        img_out = (val_img_dir if is_val else train_img_dir) / f"sar_patch_{i:04d}.tif"
        mask_out = (val_mask_dir if is_val else train_mask_dir) / f"sar_patch_{i:04d}.png"

        # Ocean background (-12 dB)
        sar_data = np.random.normal(loc=-12.0, scale=2.5, size=(256, 256)).astype(np.float32)
        mask_data = np.zeros((256, 256), dtype=np.uint8)

        # 70% chance of oil spill patch
        if np.random.rand() > 0.3:
            cx, cy = np.random.randint(60, 196, 2)
            rx, ry = np.random.randint(20, 50), np.random.randint(10, 30)
            Y, X = np.ogrid[:256, :256]
            slick = ((X - cx)**2 / rx**2 + (Y - cy)**2 / ry**2) <= 1.0
            sar_data[slick] = np.random.normal(loc=-25.0, scale=1.2, size=sar_data[slick].shape)
            mask_data[slick] = 255

        # Save GeoTIFF
        transform = from_bounds(70.0 + i*0.1, 18.0 + i*0.1, 70.1 + i*0.1, 18.1 + i*0.1, 256, 256)
        with rasterio.open(
            img_out, 'w', driver='GTiff', height=256, width=256, count=1,
            dtype=sar_data.dtype, crs='EPSG:4326', transform=transform
        ) as dst:
            dst.write(sar_data, 1)

        # Save mask PNG
        cv2.imwrite(str(mask_out), mask_data)

    print(f"  ✓ 12 Training pairs generated in: {train_img_dir}")
    print(f"  ✓ 4 Validation pairs generated in: {val_img_dir}")
    print("\n🎯 You can now test train.py directly:")
    print("   python train.py --data_dir ../../data --epochs 3 --batch_size 4\n")

def main():
    parser = argparse.ArgumentParser(description="Sentinel-1 SAR Oil Spill Dataset Helper")
    parser.add_argument("--sample", action="store_true", help="Generate quick sample dataset for instant testing")
    parser.add_argument("--download-zenodo", action="store_true", help="Download official Zenodo dataset")
    parser.add_argument("--part", type=str, default="1", choices=["1", "2", "3"], help="Zenodo Part (1, 2, or 3)")
    args = parser.parse_args()

    print("\n" + "="*65)
    print(" 🛰️  Sentinel-1 SAR Oil Spill Dataset Manager")
    print("="*65)

    if args.download_zenodo:
        part_info = ZENODO_FILES[args.part]
        print(f"\nTarget: {part_info['description']}")
        print(f"Zenodo Record ID: {part_info['record']}")
        total_gb = sum(f['size_gb'] for f in part_info['files'])
        print(f"Total download size: ~{total_gb:.1f} GB")
        print("\nNote: Zenodo files are 7z archives. Ensure you have 7z installed to extract.\n")

        for f in part_info['files']:
            dest = RAW_DIR / f['name']
            download_with_progress(f['url'], dest)
    else:
        # Default behavior: Ensure sample is ready
        create_sample_dataset()

if __name__ == "__main__":
    main()
