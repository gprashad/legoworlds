# LEGO WORLDS — Video Fidelity Plan

> **Problem:** The generated videos drift too far from the kid's actual Lego build. The magic is that it's HIS scene coming to life — not a generic Lego animation inspired by his scene.
>
> **Goal:** The output video should look like his exact Lego scene was filmed in stop-motion. Same minifigs, same vehicles, same layout, same colors. Just animated.

---

## Current State (what's wrong)

- Kie.ai VEO3 gets a text prompt + 1-2 reference photos
- The prompt describes the action + camera movement + a generic style directive
- VEO3 uses the photos as loose inspiration, not strict reference
- Result: similar vibes but wrong minifigs, wrong colors, wrong layout, different buildings
- Kid sees the video and says "that's not my scene"

---

## Root Cause

The video generation prompt is too focused on **action** and not enough on **visual fidelity**. The style directive says "maintain exact appearance from reference photo" but VEO3 treats this as a suggestion.

The current prompt:
```
{scene action} {camera angle}, {camera movement}. Stop-motion animated Lego scene, 
cinematic lighting, shallow depth of field, real Lego pieces, maintain exact 
appearance from reference photo.
```

This tells the AI what should HAPPEN but not what it should LOOK LIKE in detail.

---

## Fix Strategy: Scene-Anchored Video Prompts

### 1. Visual-First Prompts

Flip the prompt structure. Lead with EXACTLY what's in frame, then add motion.

**Before (action-first):**
```
The yellow bulldozer sits blocking the delivery area. Wide establishing shot, 
slow push-in from overhead. Stop-motion animated Lego scene...
```

**After (visual-first):**
```
A real photograph of a Lego scene on a gray baseplate: a yellow bulldozer 
with a minifig driver in orange vest sits in the center-left. A dark blue 
delivery truck with blue crates is behind it on the right. A red forklift 
is near the truck. A green and tan shop building is in the upper right corner.
12 minifigs stand in a group on the sidewalk. Gray road with yellow lane 
markings runs through the center. 

Subtle stop-motion animation: the bulldozer's arm slowly rises, the crowd 
shifts slightly, the forklift driver looks around nervously. Camera slowly 
pushes in from overhead. Real Lego pieces, real baseplate, real minifigs. 
Cinematic lighting, shallow depth of field. Nothing changes except small 
character movements.
```

### 2. Scene Bible → Video Prompt Mapping

Use the detailed scene bible (which already describes every element) to generate
visual-heavy prompts. For each screenplay scene:

```python
def build_video_prompt(scene_bible, screenplay_scene):
    # Start with the FULL visual description of what's in frame
    location = find_location(scene_bible, screenplay_scene["location"])
    characters_in_scene = find_characters(scene_bible, screenplay_scene)
    vehicles_in_scene = find_vehicles(scene_bible, screenplay_scene)
    
    prompt = f"""A real Lego scene built on a baseplate. """
    
    # Describe every visible element
    prompt += f"Setting: {location['description']}. "
    for char in characters_in_scene:
        prompt += f"{char['visual_details']} is {char['position']}. "
    for vehicle in vehicles_in_scene:
        prompt += f"A {vehicle['color']} {vehicle['type']} is visible. "
    
    # THEN add subtle motion
    prompt += f"\nSubtle stop-motion animation: {screenplay_scene['action']}. "
    prompt += f"Camera: {screenplay_scene['camera']['movement']}. "
    
    # Strict fidelity directives
    prompt += """
    CRITICAL: This must look exactly like the reference photo — same Lego pieces, 
    same colors, same layout, same baseplate. Only add subtle character movement. 
    Do NOT change the scene composition, do NOT add or remove any elements.
    Real Lego bricks, real minifigs, stop-motion style. Shallow depth of field.
    """
```

### 3. Reference Photo Strategy

Currently we send 1-2 photos. Improvements:

- **Send ALL photos** as reference (Kie.ai supports multiple `imageUrls`)
- **Pick the best photo per scene** — match screenplay scene location to the photo
  that best shows that area (the scene bible can map `reference_photo` per scene)
- **First frame anchor:** Tell VEO3 to start the video from EXACTLY the reference
  photo composition, then animate from there

### 4. Motion Constraints

The biggest drift happens when VEO3 adds too much motion. Constrain it:

- "Subtle movements only — characters shift position, heads turn, arms move"
- "The camera moves, not the scene layout"
- "No flying, no transforming, no morphing between setups"
- "The baseplate, buildings, and vehicles stay in their exact positions"
- "Only minifig limbs and heads should move"

### 5. Shorter Clips, Less Drift

VEO3 drifts more over longer durations. Currently generating 5-10 second clips.

- **Drop to 4-5 seconds per clip** — less time to drift
- **More clips, shorter each** — 6-8 clips at 4 seconds instead of 3-4 clips at 8 seconds
- **Cut on action** — each clip is one beat, one camera move

### 6. Post-Generation QA

After each clip is generated, run a quick Claude Vision check:

```python
async def check_video_fidelity(reference_photo_b64, video_first_frame_b64):
    """Ask Claude to compare reference photo vs generated video frame."""
    response = claude.messages.create(
        messages=[{
            "content": [
                {"type": "image", "source": reference_photo},
                {"type": "image", "source": video_frame},
                {"type": "text", "text": """
                    Compare these two images. The first is the original Lego build.
                    The second is a generated video frame that should match.
                    
                    Rate fidelity 1-10:
                    - Are the same minifigs present? 
                    - Are vehicles the same color and type?
                    - Is the layout/composition similar?
                    - Are buildings/structures recognizable?
                    
                    Return JSON: {"score": N, "issues": ["..."]}
                """}
            ]
        }]
    )
    # If score < 6, regenerate with adjusted prompt
```

---

## Build Order

1. **Visual-first prompts** — rewrite `build_video_prompt()` to lead with scene bible 
   visual details, constrain motion. Biggest impact, code-only change.

2. **All photos as reference** — send all input photos to Kie.ai, not just first 2.
   Pick best photo per scene based on location match.

3. **Shorter clips** — drop to 4-5 seconds, more clips per movie.

4. **Fidelity QA** — Claude Vision comparison after each clip. Auto-retry if score < 6.

---

## Example: Before vs After Prompt

### Before
```
The yellow bulldozer sits blocking the delivery area. The dark blue truck 
idles behind it. The crowd begins to gather on the sidewalk. Wide establishing 
shot, slow push-in from overhead. Stop-motion animated Lego scene, cinematic 
lighting, shallow depth of field, real Lego pieces, maintain exact appearance 
from reference photo. Smooth camera movement.
```

### After  
```
A real Lego scene on a gray baseplate photographed from above: In the 
center-left, a yellow construction bulldozer with a minifig in orange vest. 
To the right, a dark blue delivery truck loaded with blue crates. A red 
forklift sits near the truck with a minifig with orange hair. Upper right 
corner: a green and tan two-story shop with windows. A group of 12 minifigs 
in mixed clothing stands together on the gray sidewalk near the shop. Gray 
road with yellow lane markings curves through the center. Train tracks 
visible in the background.

Subtle stop-motion animation: the crowd of minifigs shifts slightly, one 
raises an arm. The bulldozer driver looks toward the crowd. Nothing else 
moves. Camera slowly pushes in from overhead toward the crowd.

STRICT: Match the reference photo exactly. Same pieces, same colors, same 
layout. Real Lego bricks on a real baseplate. Only minifig limbs move. 
Shallow depth of field, warm cinematic lighting.
```
