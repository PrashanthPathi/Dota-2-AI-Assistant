# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-0bcf0a7c7b38"
ITEMS_COLLECTION = "equipment_and_spells"

SAMPLE_ITEMS = [
    {
        "id": "vorpal-sword",
        "name": "Vorpal Sword",
        "type": "weapon",
        "rarity": "Legendary",
        "description": "A legendary blade that snicker-snacks through armor and severes necks on critical hits.",
        "cost_gp": 50000,
        "damage": "1d8+3 slashing",
        "properties": ["finesse", "versatile", "magical"],
    },
    {
        "id": "healing-potion",
        "name": "Potion of Greater Healing",
        "type": "potion",
        "rarity": "Uncommon",
        "description": "A murky red fluid that glimmers when agitated. Restores 4d4 + 4 hit points when consumed.",
        "cost_gp": 150,
        "damage": "n/a",
        "properties": ["consumable"],
    },
    {
        "id": "fireball-scroll",
        "name": "Scroll of Fireball",
        "type": "spell_scroll",
        "rarity": "Rare",
        "description": "A bright streak flashes from your pointing finger into a 20-foot radius sphere of fiery explosion dealing 8d6 fire damage.",
        "cost_gp": 300,
        "damage": "8d6 fire",
        "properties": ["3rd-level evocation", "somatic", "verbal", "material"],
    },
    {
        "id": "boots-of-elvenkind",
        "name": "Boots of Elvenkind",
        "type": "wondrous_item",
        "rarity": "Uncommon",
        "description": "While you wear these boots, your steps make no sound, granting advantage on Stealth checks.",
        "cost_gp": 400,
        "damage": "n/a",
        "properties": ["requires attunement", "stealth advantage"],
    },
    {
        "id": "cloak-of-invisibility",
        "name": "Cloak of Invisibility",
        "type": "wondrous_item",
        "rarity": "Legendary",
        "description": "A gossamer cloak that renders its wearer completely invisible when the hood is pulled up.",
        "cost_gp": 75000,
        "damage": "n/a",
        "properties": ["requires attunement", "invisibility"],
    },
]


def seed():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(ITEMS_COLLECTION)

    for item in SAMPLE_ITEMS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"Seeded item: {item['name']} ({doc_id})")

    print(f"Successfully seeded {len(SAMPLE_ITEMS)} items into '{ITEMS_COLLECTION}'.")


if __name__ == "__main__":
    seed()
