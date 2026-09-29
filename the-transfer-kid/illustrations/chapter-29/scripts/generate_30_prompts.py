#!/usr/bin/env python3
import os
from pathlib import Path

STYLE = """STYLE

Semi-realistic cinematic digital painting, American graphic novel / editorial concept-art aesthetic, painterly brushwork, realistic human anatomy and facial features, natural skin texture, dramatic cinematic lighting with deep shadows and subtle highlights, muted earthy color palette (rust, olive, dust brown, cool dusk blue), atmospheric depth, realistic contemporary Los Angeles environments, expressive but restrained facial expressions, detailed yet painterly rendering, slightly gritty film-grain texture, sophisticated editorial concept art, grounded realism, cinematic color grading. Subjects are ordinary lean-built young adults, NOT bodybuilders: slim-athletic or average build only, no exaggerated muscle definition, no adult gym physique. The reference image supplied with this prompt establishes facial likeness only — the face, the hair colour and the build. Clothing, headwear, jewellery and props are exactly as written in the text above and NOT as they appear in the reference image; ignore any garment or headwear the reference happens to show. Not anime, not manga, not cartoon, not photorealistic photo, not glossy 3D render. Any lettering in the image must be spelled exactly as specified and rendered as clean hand-lettered American graphic-novel text; do not invent any additional words, signage, captions, logos or watermarks anywhere in the frame."""

CHAR_JUSTIN = """JUSTIN — Young man with shaggy golden-blond hair, slightly wavy, falling messy over his forehead and curling past his ears; fair sun-flushed skin with faint freckles across the nose; straight nose with a small silver nose ring in the right nostril; several small silver hoop earrings in both ears; full mouth, soft jaw, tired green-hazel eyes; slim build. Bare-headed — no hat, no cap, nothing on his head, his messy hair fully visible. He wears a plain washed-out olive tee under an oversized charcoal-grey zip hoodie, dark jeans and scuffed low-top sneakers. The knuckles of his right hand are swollen and mottled dark red and blue."""

CHAR_MARCUS = """MARCUS — Young man with textured ash-blond hair over visibly darker roots, cut short at the sides with a choppy piecey fringe swept across the forehead, squarer jaw than Justin, fair skin, light gray-green eyes, one small silver hoop in his left ear, medium athletic build. Bare-headed — no hat, no cap, nothing on his head. He wears a faded heather-gray crewneck sweatshirt and dark sweatpants. Along his left lower jawline is a white sterile butterfly bandage surrounded by dark purple and yellow bruising. His lower lip is swollen on the left side. Steady, level, unbothered expression."""

CHAR_MOM = """JUSTIN'S MOTHER — Latina woman in her forties, dark hair pulled back in a loose clip with stray strands around her ears, wearing dark navy blue hospital scrubs with a laminated hospital ID badge, deeply fatigued and tired expression, curved shoulders."""

SHOTS = [
    ("01-morning-keys", "Eye-level interior shot of an apartment entryway at 5:40 AM. Dim dawn light filtering from a hallway window onto worn gray linoleum. A heavy metal front door is slightly cracked open with a brass key ring resting in the lock.", "", []),
    ("02-ceiling-insomnia", "Interior low-angle shot in a dark teen bedroom before dawn. JUSTIN lies awake on his back on an unmade bed, staring up with tired, sleepless eyes at a faint rectangle of yellow streetlamp light cast across the white ceiling.", "", ["JUSTIN"]),
    ("03-memory-punch-recall", "Dark, moody psychological flashback impression. In a high-contrast cafeteria setting, a blurry impression of Marcus falling backward off a gray chair amidst spilled trays, haunted by guilt and shame.", "", ["JUSTIN", "MARCUS"]),
    ("04-entryway-clogs", "Low-angle shot of the apartment entryway shoe rack at dawn. A pair of heavy navy-blue hospital support clogs rests on the linoleum baseboard beside a dropped black nylon tote bag.", "", []),
    ("05-answering-machine-idle", "Close-up shot of a 1990s-era silver plastic telephone answering machine beside a kitchen microwave. A red digital 7-segment LED display glows with the number '1', and a red LED light blinks once every two seconds in the quiet morning.", "The digital LED display reads '1' in bright red digital segment font.", []),
    ("06-answering-machine-playing", "Tight macro shot of the silver telephone answering machine with the small cassette tape relay mechanism turning smoothly under the acrylic window while audio plays through the front speaker grille.", "", []),
    ("07-bruised-hand-swelling", "Close-up shot of JUSTIN's right hand hanging down by his side. The knuckles are visibly mottled with dark eggplant-purple and blue bruising, slightly stiff and swollen, set against his dark jeans.", "", ["JUSTIN"]),
    ("08-hallway-shadow", "Wide shot looking down a short apartment hallway in the blue dawn light. JUSTIN in socks and grey hoodie walks cautiously toward the kitchen, his shadow stretching long across the floorboards.", "", ["JUSTIN"]),
    ("09-mother-counter-dawn", "Medium wide shot of an unlit apartment kitchen at dawn. JUSTIN'S MOTHER stands in navy hospital scrubs by the counter, leaning her weight heavily on both hands, head bowed in bone-deep fatigue under the cool blue dawn window light.", "", ["MOM"]),
    ("10-mother-gaze-hand", "Tight over-the-shoulder shot from behind Justin's mother, looking down at JUSTIN standing in the kitchen doorway, her tired eyes tracking down to his bruised, discolored right hand.", "", ["MOM", "JUSTIN"]),
    ("11-kitchen-stillness-two-shot", "Cinematic two-shot in the dim dawn kitchen. Justin's mother stands by the counter looking down, while JUSTIN stands across from her with his head bowed and shoulders slumped in heavy silence.", "", ["MOM", "JUSTIN"]),
    ("12-memory-childhood-rug", "Warm, nostalgic flashback scene in a sunlit living room from years ago. Two young boys (elementary school age) doing homework side by side on a colorful living room rug, with glass casserole dishes on the table behind them.", "", []),
    ("13-mother-setting-badge", "Close-up shot of Justin's mother's tired hands unclipping her plastic hospital triage badge and setting it down gently on the laminate kitchen counter next to a ring of car keys.", "", ["MOM"]),
    ("14-bedroom-sunlight-morning", "Interior wide shot of the bedroom at 8:30 AM. Bright golden morning sunlight cuts sharp diagonal yellow stripes through vertical window blinds across the unmade bed and carpet floor.", "", []),
    ("15-school-absence-contrast", "Wide atmospheric shot of an empty, bright suburban high school hallway during class time. Lockers line the walls under fluorescent lights, classroom doors closed with students faintly visible inside, completely peaceful.", "", []),
    ("16-phone-screen-contacts", "Close-up shot of a smartphone screen held in a hand. The screen shows a contacts list with 'Marcus Watts' highlighted at the top, surrounded by unread message notification badges from a group chat.", "The phone screen displays the name 'Marcus Watts' prominently.", ["JUSTIN"]),
    ("17-shoes-hoodie-prep", "Low-angle shot in the bedroom. JUSTIN sits on the edge of the mattress tying the white laces of his scuffed sneakers, pulling the zipper of his charcoal-grey hoodie up, getting ready to leave.", "", ["JUSTIN"]),
    ("18-empty-neighborhood-street", "Outdoor tracking shot of a quiet suburban Los Angeles residential street at 9:00 AM. Wide empty asphalt road, trimmed palm trees, single-story stucco houses with patchy lawns, crisp winter sky.", "", []),
    ("19-memory-kicking-cans", "Sunny nostalgic flashback scene. Two middle-school boys walking side by side down a sunlit sidewalk, laughing as one kicks a crushed soda can along the pavement without letting it roll into the gutter.", "", []),
    ("20-marcus-house-exterior", "Exterior wide shot of Marcus's house on the corner of Elm and Valencia. A neat single-story California stucco house with a manicured front lawn, short brick porch with two white chairs, and an empty driveway.", "", []),
    ("21-doorbell-hesitation", "Close-up shot of a brass doorbell on a white doorframe. JUSTIN's left hand hesitates in mid-air for a moment before pressing the round brass button in the morning sun.", "", ["JUSTIN"]),
    ("22-door-unlocking", "POV looking at the white wooden front door as two deadbolts audibly click open from the inside and the door begins to swing slowly inward.", "", []),
    ("23-marcus-doorway-face", "Medium portrait shot looking into the doorway. MARCUS stands in the doorframe wearing a gray crewneck sweatshirt. A white butterfly bandage is taped along his bruised left jawline, his lower lip swollen, eyes level and unblinking.", "", ["MARCUS"]),
    ("24-porch-facing-each-other", "Medium wide cinematic two-shot on the short brick porch. MARCUS leans back against the doorframe, while JUSTIN stands two steps below on the concrete path, looking up with genuine remorse.", "", ["JUSTIN", "MARCUS"]),
    ("25-justin-looking-down", "Close-up on JUSTIN's face, eyes cast down at the painted concrete porch, speaking with honest, unvarnished vulnerability, swallowing his pride completely.", "", ["JUSTIN"]),
    ("26-showing-injured-knuckles", "Close-up shot of JUSTIN extending his right hand in the morning sunlight, showing his swollen, discolored purple knuckles openly without hiding.", "", ["JUSTIN"]),
    ("27-marcus-touching-bandage", "Close-up on MARCUS's face as he brings two fingers up to lightly touch the medical tape on his jaw, wincing slightly with a dry, sharp expression.", "", ["MARCUS"]),
    ("28-marcus-cold-truth", "Medium shot of MARCUS looking directly forward with steady intensity, delivering the cold, principled truth about saving their nine-year friendship from expulsion.", "", ["MARCUS"]),
    ("29-door-latching-unlocked", "Close-up of the white front door pulling shut until the brass latch clicks into the strike plate, leaving the deadbolt thumb-turn in the horizontal unlocked position.", "", []),
    ("30-walking-down-valencia", "Wide outdoor tracking shot looking down Valencia street. JUSTIN walks away from the house in bright morning sunlight, shoulders looser, casting a long crisp shadow forward along the pavement.", "", ["JUSTIN"]),
]

prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
prompts_dir.mkdir(parents=True, exist_ok=True)

for name, scene, lettering, chars in SHOTS:
    p_file = prompts_dir / f"{name}.md"
    content = []
    content.append("SCENE\n")
    content.append(scene.strip() + "\n")
    if lettering:
        content.append("\nLETTERING\n")
        content.append(lettering.strip() + "\n")
    
    char_blocks = []
    for c in chars:
        if c == "JUSTIN":
            char_blocks.append(CHAR_JUSTIN)
        elif c == "MARCUS":
            char_blocks.append(CHAR_MARCUS)
        elif c == "MOM":
            char_blocks.append(CHAR_MOM)
    
    if char_blocks:
        content.append("\nCHARACTERS\n")
        content.append("\n\n".join(char_blocks) + "\n")
    
    content.append("\n" + STYLE.strip() + "\n")
    
    p_file.write_text("\n".join(content), encoding="utf-8")

print(f"Generated {len(SHOTS)} prompt files in {prompts_dir}")
