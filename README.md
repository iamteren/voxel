# Voxel Generator

A Python-based agentic pipeline for generating voxel 3D assets for YouTube Shorts production.

---

## Pipeline

| Step | Tool | Description |
|------|------|-------------|
| 1 | Writing Agent | AI generates scene scripts and asset prompts |
| 2 | voxel_generator.py | Builds .vox and .obj files |
| 3 | MagicaVoxel | Lighting, shadows, POV framing |
| 4 | Blender | Animation and rendering |
| 5 | CapCut | Final edit and publish |

---

## Project Structure

    voxel/
    ├── voxel_generator.py
    ├── voxel_generator.py.bak
    └── exports/
        ├── kitchen_scene.vox
        ├── kitchen_scene.obj
        ├── kitchen_scene_2.vox
        ├── kitchen_scene_2.obj
        ├── viewer.html
        └── viewer_standalone.html

---

## Usage

    python3 voxel_generator.py

## Sync Exports to S3

    aws s3 sync ~/voxel/exports/ s3://voxel-exports-iamteren/

---

## Storage

- **GitHub:** https://github.com/iamteren/voxel
- **S3 Bucket:** s3://voxel-exports-iamteren
