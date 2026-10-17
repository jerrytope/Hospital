"""Stock photos for the demo content, and which photo goes where.

The files live in apps/core/fixtures/demo_photos/<key>.jpg. Every photo comes from Unsplash under the Unsplash
License (free for commercial use, no attribution required). The id is the images.unsplash.com photo id, so a
file can be fetched again from https://images.unsplash.com/photo-<id>?w=1600&q=80.

These are stand-ins so the site looks real while it is being built. Replace them with your own field photos,
taken with the informed consent of everyone shown, before launch.

Used by `seed_demo` (new sites) and `use_demo_photos` (swaps the old gradient placeholders on an existing site).
"""
from pathlib import Path

PHOTO_DIR = Path(__file__).resolve().parent / "fixtures" / "demo_photos"

# key: (Unsplash photo id, alt text)
PHOTOS = {
    "doctor_patient": ("1536064479547-7ee40b74b807", "A doctor in a white coat talks with a young girl across a clinic desk"),
    "doctor_bp": ("1631815588090-d4bfec5b1ccb", "A doctor checks a smiling woman's blood pressure"),
    "nurse_patient": ("1691139601099-932c01ec198b", "A nurse in a face mask examines a patient"),
    "surgical_team": ("1579684453423-f84349ef60b0", "A surgical team operates on a patient"),
    "hospital_ward": ("1538108149393-fbbd81895907", "Clean, made-up beds in a hospital ward"),
    "health_workers": ("1783408355447-b01a88767e6a", "Two health workers in green scrubs walk along a busy town street"),
    "nurse_portrait": ("1761234852472-85aeea9c3eac", "A nurse in green scrubs with a stethoscope"),
    "founder": ("1678695972687-033fa0bdbac9", "A smiling doctor in a white coat with a stethoscope"),
    "ceo": ("1631131431211-4f768d89087d", "A smiling man in a blue suit standing outdoors"),
    "lab": ("1579165466949-3180a3d056d5", "A laboratory scientist uses a pipette to test samples"),
    "mother_child": ("1735792339621-2846f164b78f", "A mother smiles at her young son as they sit together on a bed"),
    "mother_baby_back": ("1487546331507-fcf8a5d27ab3", "A mother in a headwrap carries her baby on her back"),
    "mother_newborn": ("1746766414005-ee349f5f12bf", "A mother holds her baby while waiting outside a health centre"),
    "newborn": ("1555252333-9f8e92e65df9", "A newborn baby's feet peek out of a soft white blanket"),
    "water_children": ("1543181077-099f32f30a1c", "Children carry water containers along a dirt road"),
    "water_women": ("1553775927-a071d5a6a39a", "Three women carry basins on their heads along a dry dirt road"),
    "jerrycans": ("1543335547-334c05de28c2", "A man sits on yellow water jerrycans"),
    "unsafe_water": ("1649263706080-307fc9d2bd50", "A hand dips a cup into a muddy puddle of water"),
    "flood_camp": ("1727475807090-f1c30f6c294f", "A woman wades through a flooded camp past damaged shelters"),
    "flood_tents": ("1728320764872-2eebb4f95e4e", "Tents standing in floodwater"),
    "flood_street": ("1617494532674-67d22df2addb", "People wade through a flooded street"),
    "camp_aerial": ("1728320771441-17a19df0fe4c", "An aerial view of a large camp for displaced families"),
    "camp_child": ("1763125085488-99acd00cdea7", "A child stands in a muddy, flooded camp among tents"),
    "earthquake": ("1677233860259-ce1a8e0f8498", "A building collapsed by an earthquake"),
    "rubble": ("1702024249908-3d04f2c22d71", "Rubble from collapsed buildings beside a road"),
    "ukraine": ("1704971143833-250c9efb7c9e", "People clear debris in front of a damaged apartment block"),
    "crowd_mother": ("1781263409522-06f1d4a6f3af", "A smiling woman in a headscarf holds a child among a crowd of families"),
    "feeding_child": ("1694286068362-5dcea7ed282a", "A health worker feeds a young child"),
    "children_meal": ("1620608929452-ccc05381b0f7", "Children eat a meal together at long tables"),
    "children_group": ("1509099836639-18ba1795216d", "A group of smiling children"),
    "children_road": ("1520254553641-2eed4cf2ef26", "Children walk along a dusty village road"),
    "classroom": ("1473649085228-583485e6e4d7", "Children study at wooden desks in a classroom"),
    "classroom_writing": ("1567057420215-0afa9aa9253a", "Children write in their exercise books"),
    "community_woman": ("1694286066858-462538cd9886", "A smiling young woman in her village"),
    "three_women": ("1694286080685-279d3b3c8dfb", "Three smiling young women sit side by side"),
    "conversation": ("1759593047536-5258c3c6a527", "Two women talk together on a bench outdoors"),
    "hands": ("1604881991720-f91add269bed", "Two people hold hands across a table in comfort"),
    "medkit": ("1624638764471-cffef5035746", "An aid worker unpacks an emergency medical kit"),
    "iv_prep": ("1624638742121-32c6214bddd8", "A health worker prepares an intravenous drip"),
    "loading_aid": ("1786719664233-f7adaf17393a", "Volunteers load sacks of supplies into a truck"),
    "vaccine": ("1618015359417-89be02e0089f", "Vials of vaccine"),
    "medicines": ("1631549916768-4119b2e5f926", "Blister packs of medicines"),
    "mosquito_net": ("1747056032562-1c73b853a79d", "A bed protected by a mosquito net"),
    "solar_lamp": ("1774265537519-05c29a22bc32", "A solar-powered lantern hangs from a tree"),
    "wheelchair": ("1565615833231-e8c91a38a012", "A woman in a wheelchair on a garden path"),
    "older_couple": ("1718010588689-9806ce642d39", "An older couple laugh together"),
    "coins": ("1532629345422-7515f3d16bb6", "Cupped hands hold coins and a note reading 'make a change'"),
    "runners": ("1452626038306-9aae5e071dd3", "Runners in a city road race"),
    "volunteer": ("1559027615-cd4628902d4a", "A volunteer in a bright volunteer shirt at an event"),
    "history_nurses": ("1758575514475-2a84975db58e", "Archive photo of a line of nurses in uniform"),
    "history_care": ("1758653500481-a1b46b5b63d4", "Archive photo of a nurse caring for a patient in bed"),
}

# --- where each photo goes ----------------------------------------------------------------

HOME_HERO = "doctor_patient"
SHARE_IMAGE = "doctor_patient"

# Section and landing pages, by slug.
PAGE_HEROES = {
    "who-we-are": "surgical_team",
    "what-we-do": "nurse_patient",
    "where-we-work": "children_road",
    "get-involved": "children_group",
    "mission": "community_woman",
    "our-history": "history_nurses",
    "our-approach": "health_workers",
    "emergencies": "flood_tents",
    "gifts": "crowd_mother",
}

PROGRAMS = {
    "Emergency Response": "iv_prep",
    "Health Services Support": "doctor_bp",
    "Family and Community Health": "mother_baby_back",
    "Women's and Children's Health": "mother_child",
    "Mental Health": "conversation",
    "Water, Sanitation and Hygiene": "water_children",
    "Nutrition and Food Security": "feeding_child",
}

EMERGENCIES = {
    "Flood Response in the Lake Chad Basin": "flood_camp",
    "Cholera Outbreak Response": "unsafe_water",
    "Earthquake Relief": "earthquake",
    "Sahel Hunger Crisis": "water_women",
    "Displacement Crisis in Sudan": "camp_aerial",
    "War in Ukraine": "ukraine",
    "Syria Crisis": "camp_child",
}

# Story title: (hero photo, photo inside the story body)
STORIES = {
    "A Midwife's Night in the Flood Zone": ("mother_newborn", "flood_street"),
    "Clean Water Returns to Kalemie": ("water_children", "jerrycans"),
    "Learning to Heal: Counselling After Conflict": ("conversation", "hands"),
    "The Mobile Clinic That Reached the Mountains": ("rubble", "health_workers"),
    "Treating Malnutrition Before It's Too Late": ("feeding_child", "children_meal"),
    "Nurses Who Became Trainers": ("three_women", "nurse_portrait"),
    "Situation Update: Lake Chad Basin Floods": ("flood_camp", "flood_tents"),
    "Cholera Response: Week Six": ("unsafe_water", "lab"),
    "Video: A Day with Our Mobile Medical Team": ("doctor_bp", "medkit"),
    "Press Release: Emergency Teams Deploy to Flood-Affected Areas": ("loading_aid", "iv_prep"),
    "Press Release: New Maternal Health Program Launched": ("mother_child", "newborn"),
    "Supporter Profile: Running 100 km for Clean Water": ("runners", "water_women"),
    "A School Turned Health Post": ("classroom", "classroom_writing"),
    "Snapshots From the Field": ("children_group", "community_woman"),
}

# Country heroes cycle through photos that suit the region.
REGION_POOLS = {
    "Africa": ["children_road", "water_women", "community_woman", "mother_baby_back", "crowd_mother", "three_women",
               "classroom", "health_workers", "water_children", "jerrycans", "children_group", "mother_newborn"],
    "Asia": ["flood_street", "earthquake", "camp_aerial", "children_meal", "classroom_writing", "flood_tents"],
    "Middle East": ["camp_child", "camp_aerial", "rubble", "conversation", "children_meal"],
    "Europe": ["ukraine", "conversation"],
    "Americas": ["rubble", "community_woman", "children_group", "doctor_bp"],
}
DEFAULT_POOL = REGION_POOLS["Africa"]

# Homepage impact rows, in order.
IMPACT_ROWS = ["children_group", "nurse_patient", "mother_child", "water_children",
               "health_workers", "lab", "conversation", "children_meal"]

# History timeline entries, in order (1990 ... today).
TIMELINE = ["history_nurses", "camp_aerial", "children_group", "flood_street", "rubble", "health_workers",
            "lab", "earthquake", "unsafe_water", "vaccine", "earthquake", "doctor_patient"]

GIFTS = {
    "Emergency medical kit": "medkit",
    "Clean water for a family": "jerrycans",
    "Safe birth kit": "newborn",
    "Nutrition treatment for a child": "children_meal",
    "Train a community health worker": "three_women",
    "Hygiene kits for 5 families": "loading_aid",
    "Vaccines for 20 children": "vaccine",
    "Counselling sessions": "hands",
    "Mosquito nets for a village": "mosquito_net",
    "Solar lamp for a clinic": "solar_lamp",
    "Wheelchair": "wheelchair",
    "Stock a pharmacy": "medicines",
}

PEOPLE = {"Dr. Amara Placeholder": "founder", "Tunde Example": "ceo"}

# Annual report covers, newest first.
REPORT_COVERS = ["children_group", "doctor_bp", "mother_child", "water_children"]

# Cards and tabs inside StreamFields (menus, history page links, Get Involved tabs), by title.
CARDS = {
    "Watch our story": "health_workers",
    "Global Ambassadors": "three_women",
    "Our History": "history_care",
    "Donate": "doctor_patient",
    "Gifts of Hope": "medkit",
    "Get Involved": "volunteer",
    "Honour & Memorial Giving": "hands",
    "Where We Work": "children_road",
    "What We Do": "nurse_patient",
    "Gifts catalog": "medkit",
    "Tribute giving": "hands",
    "Planned giving": "older_couple",
    "Stocks": "coins",
}


def country_key(region_name, index):
    pool = REGION_POOLS.get(region_name, DEFAULT_POOL)
    return pool[index % len(pool)]


def get_photo(key):
    """Return the library image for a photo key, adding it to the image library the first time."""
    from django.core.files.images import ImageFile

    from apps.core.models import CustomImage

    photo_id, alt = PHOTOS[key]
    credit = f"Unsplash (photo-{photo_id})"
    image = CustomImage.objects.filter(credit=credit).first()
    if image:
        return image
    with open(PHOTO_DIR / f"{key}.jpg", "rb") as fh:
        image = CustomImage(title=f"Sample photo: {alt}", alt_text=alt, credit=credit, consent_obtained=False)
        image.file = ImageFile(fh, name=f"{key}.jpg")
        image.save()
    return image
