import struct
import boto3
import json
import re
from pydantic import BaseModel, Field
from typing import List


# ─── Pydantic Models ───────────────────────────────────────────────────────────

class Scene(BaseModel):
    scene_number: int
    asset_prompt: str = Field(description="Exact prompt to generate the 3D voxel asset")
    camera: str = Field(description="Camera angle and movement instructions")
    voiceover: str = Field(description="Voiceover script for this scene")

class StoryScript(BaseModel):
    title: str
    duration_seconds: int
    scenes: List[Scene]

    def display(self):
        print("\n" + "═" * 60)
        print(f"  {self.title}")
        print(f"  Duration: {self.duration_seconds}s  |  Scenes: {len(self.scenes)}")
        print("═" * 60)
        for scene in self.scenes:
            print(f"\n  SCENE {scene.scene_number}")
            print("  " + "─" * 40)
            print(f"  ASSET PROMPT\n  {scene.asset_prompt}")
            print(f"\n  CAMERA\n  {scene.camera}")
            print(f"\n  VOICEOVER\n  \"{scene.voiceover}\"")
        print("\n" + "═" * 60 + "\n")


# ─── Voxel Builder ─────────────────────────────────────────────────────────────

class VoxelAssetBuilder:
    def __init__(self, size_x=32, size_y=32, size_z=32):
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.grid = {}

    def generate_story_script(self, story_prompt: str) -> StoryScript:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        system_prompt = """You are a YouTube Shorts storytelling agent and Creative Director.
Given a story prompt, return ONLY a valid JSON object with this exact structure:
{
  "title": "short title of the story",
  "duration_seconds": 45,
  "scenes": [
    {
      "scene_number": 1,
      "asset_prompt": "exact prompt to generate the 3D voxel asset",
      "camera": "camera angle and movement description",
      "voiceover": "voiceover script for this scene"
    }
  ]
}
Rules:
- Always return exactly 4 scenes.
- Keep each voiceover under 2 sentences.
- Asset prompts must be specific and visual.
- Return ONLY raw JSON. No markdown, no code fences, no explanation."""

        response = client.invoke_model(
            modelId="us.amazon.nova-lite-v1:0",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": story_prompt}]}],
                "system": [{"text": system_prompt}],
                "inferenceConfig": {"maxTokens": 2048, "temperature": 0.7}
            }),
            contentType="application/json",
            accept="application/json"
        )

        body = json.loads(response["body"].read())
        raw_text = body["output"]["message"]["content"][0]["text"].strip()
        clean = re.sub(r"```(?:json)?|```", "", raw_text).strip()

        data = json.loads(clean)
        script = StoryScript(**data)
        return script

    def generate_voxels_from_ai(self, prompt: str):
        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        system_prompt = """You are a 3D voxel scene generator. Given a text description, return ONLY a valid JSON object.
The JSON must be a flat dictionary where each key is a comma-separated "x,y,z" coordinate string (integers 0-31),
and each value is a palette color index integer (1-255).
Rules:
- Grid is 32x32x32. All coordinates must be within 0-31.
- Use color index 42 for wood/brown, 15 for metallic/silver, 1 for generic objects.
- Generate AT LEAST 200 voxels.
- Return ONLY the raw JSON object. No explanation, no markdown, no code fences."""

        response = client.invoke_model(
            modelId="us.amazon.nova-lite-v1:0",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "system": [{"text": system_prompt}],
                "inferenceConfig": {"maxTokens": 5120, "temperature": 0.2}
            }),
            contentType="application/json",
            accept="application/json"
        )

        body = json.loads(response["body"].read())
        raw_text = body["output"]["message"]["content"][0]["text"].strip()
        clean = re.sub(r"```(?:json)?|```", "", raw_text).strip()

        try:
            raw_dict = json.loads(clean)
        except json.JSONDecodeError:
            last_comma = clean.rfind(',')
            if last_comma != -1:
                clean = clean[:last_comma] + "\n}"
            raw_dict = json.loads(clean)
            print("[Warning] Response truncated - recovered partial voxel data.")

        voxel_grid = {}
        for key, color_idx in raw_dict.items():
            x, y, z = map(int, key.split(","))
            if 0 <= x <= 31 and 0 <= y <= 31 and 0 <= z <= 31:
                voxel_grid[(x, y, z)] = int(color_idx)

        print(f"[Nova] Parsed {len(voxel_grid)} voxels from model response.")
        self.grid = voxel_grid

    def export_to_vox(self, filename: str):
        if not self.grid:
            print("[Error] Grid is empty.")
            return

        header = b'VOX \x96\x00\x00\x00'
        size_content = struct.pack('<III', self.size_x, self.size_y, self.size_z)
        size_chunk = b'SIZE' + struct.pack('<II', len(size_content), 0) + size_content

        num_voxels = len(self.grid)
        xyzi_content = struct.pack('<I', num_voxels)
        for (x, y, z), color_idx in self.grid.items():
            xyzi_content += struct.pack('<BBBB', x, y, z, color_idx)
        xyzi_chunk = b'XYZI' + struct.pack('<II', len(xyzi_content), 0) + xyzi_content

        main_children_size = len(size_chunk) + len(xyzi_chunk)
        main_chunk = b'MAIN' + struct.pack('<II', 0, main_children_size) + size_chunk + xyzi_chunk

        with open(filename, 'wb') as f:
            f.write(header + main_chunk)
        print(f"[Export] Saved: {filename}")

    def export_to_obj(self, filename: str):
        if not self.grid:
            print("[Error] Grid is empty.")
            return

        vertices, faces = [], []
        vertex_count = 1
        offsets = [
            (0,0,0),(1,0,0),(1,1,0),(0,1,0),
            (0,0,1),(1,0,1),(1,1,1),(0,1,1)
        ]
        face_indices = [
            (0,1,2,3),(4,5,6,7),
            (0,1,5,4),(2,3,7,6),
            (0,3,7,4),(1,2,6,5)
        ]
        for (x, y, z) in self.grid.keys():
            for dx, dy, dz in offsets:
                vertices.append(f"v {float(x+dx)} {float(y+dy)} {float(z+dz)}\n")
            for fi in face_indices:
                faces.append(f"f {vertex_count+fi[0]} {vertex_count+fi[1]} {vertex_count+fi[2]} {vertex_count+fi[3]}\n")
            vertex_count += 8

        with open(filename, 'w') as f:
            f.writelines(vertices)
            f.writelines(faces)
        print(f"[Export] Saved: {filename}")


# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    print("\n" + "═" * 60)
    print("  VOXEL GENERATOR — Agentic Pipeline")
    print("═" * 60)
    print("\n  Mode:")
    print("  1. Story Agent  — generate script + storyboard")
    print("  2. Voxel Build  — generate .vox + .obj from prompt")
    print("  3. Full Run     — story agent then build scene 1\n")

    mode = input("  Select mode (1/2/3): ").strip()

    builder = VoxelAssetBuilder()

    if mode == "1":
        story_prompt = input("\n  Story prompt: ").strip()
        script = builder.generate_story_script(story_prompt)
        script.display()

    elif mode == "2":
        prompt        = input("\n  Scene prompt: ").strip()
        output_name   = input("  Output name (no extension): ").strip()
        output_folder = input("  Output folder (default ./exports): ").strip() or "./exports"
        os.makedirs(output_folder, exist_ok=True)
        builder.generate_voxels_from_ai(prompt)
        builder.export_to_vox(os.path.join(output_folder, f"{output_name}.vox"))
        builder.export_to_obj(os.path.join(output_folder, f"{output_name}.obj"))

    elif mode == "3":
        story_prompt  = input("\n  Story prompt: ").strip()
        output_name   = input("  Output name (no extension): ").strip()
        output_folder = input("  Output folder (default ./exports): ").strip() or "./exports"
        os.makedirs(output_folder, exist_ok=True)

        script = builder.generate_story_script(story_prompt)
        script.display()

        print("  [Building voxels for Scene 1...]\n")
        builder.generate_voxels_from_ai(script.scenes[0].asset_prompt)
        builder.export_to_vox(os.path.join(output_folder, f"{output_name}.vox"))
        builder.export_to_obj(os.path.join(output_folder, f"{output_name}.obj"))

    else:
        print("\n  Invalid mode selected.")
