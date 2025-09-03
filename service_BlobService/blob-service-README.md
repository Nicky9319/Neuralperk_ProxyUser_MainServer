# Blob Storage Service

## Overview
The blob storage service manages three main buckets for storing different types of files:

1. **Blend Files** - For storing .blend files
2. **Rendered Videos** - For storing rendered video files
3. **Rendered Frames** - For storing rendered image frames

## Storage Structure

### 1. Blend Files Bucket
**Path Convention:** `customer_id/object_id/blend_file_name.blend`

**Example:**
```
customer_123/
└── object_456/
    └── character_model.blend
```

### 2. Rendered Videos Bucket
**Path Convention:** `customer_id/object_id/video.mp4`

**Example:**
```
customer_123/
└── object_456/
    └── video.mp4
```

### 3. Rendered Frames Bucket
**Path Convention:** `customer_id/object_id/frame_number.png`

**Example:**
```
customer_123/
└── object_456/
    ├── 001.png
    ├── 002.png
    ├── 003.png
    └── ...
```

## File Naming Rules

- **Customer ID**: Unique identifier for each customer
- **Object ID**: Unique identifier for each 3D object/project
- **Blend Files**: Use descriptive names with `.blend` extension
- **Videos**: Always named `video.mp4`
- **Frames**: Sequential numbering with `.png` extension (001.png, 002.png, etc.)

## Usage Notes

- Each customer can have multiple objects
- Each object can have one blend file, one video, and multiple frames
- Frame numbers should be zero-padded (001, 002, 003, etc.)
- All paths are case-sensitive
