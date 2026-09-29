# ruff: noqa
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

import os
import random
import time
import urllib.parse
import urllib.request
import json
from typing import Any, Dict, List, Optional
from google import genai
from google.cloud import firestore, storage
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

MODEL = "gemini-3.6-flash"

# Hardcoded Project ID and Cloud Storage Bucket strings to avoid project number issues on Agent Platform
PROJECT_ID = "qwiklabs-gcp-04-0bcf0a7c7b38"
ASSETS_BUCKET = "realm-master-assets-qwiklabs-gcp-04-0bcf0a7c7b38"
ITEMS_COLLECTION = "equipment_and_spells"

_firestore_client = None
_storage_client = None
_genai_client = None


def get_firestore_client() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=PROJECT_ID)
    return _firestore_client


def list_items(item_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists equipment, items, and spells available in the realm catalog.

    Args:
        item_type: Optional filter by item type (e.g. 'weapon', 'potion', 'spell_scroll', 'wondrous_item').

    Returns:
        A list of item dictionaries containing name, type, rarity, cost, damage, and description.
    """
    db = get_firestore_client()
    col_ref = db.collection(ITEMS_COLLECTION)
    
    if item_type:
        docs = col_ref.where("type", "==", item_type.lower()).stream()
    else:
        docs = col_ref.stream()

    items = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        items.append(data)
    return items


def search_item(name: str) -> Dict[str, Any]:
    """Searches for a specific item, spell, or piece of equipment by name.

    Args:
        name: Name of the item or spell (case-insensitive substring or exact match).

    Returns:
        The matched item dictionary or a not found message.
    """
    db = get_firestore_client()
    docs = db.collection(ITEMS_COLLECTION).stream()
    target = name.lower()

    for doc in docs:
        item = doc.to_dict()
        if target in item.get("name", "").lower() or target in doc.id.lower():
            item["id"] = doc.id
            return item
    return {"error": f"Item or spell '{name}' not found in the realm archives."}


def create_or_update_item(
    name: str,
    item_type: str,
    rarity: str,
    cost_gp: int,
    description: str,
    damage: str = "n/a",
    properties: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Creates a new magical item, weapon, or spell in the realm database.

    Args:
        name: The name of the item or spell.
        item_type: Category (e.g., 'weapon', 'potion', 'spell_scroll', 'armor', 'wondrous_item').
        rarity: Rarity tier ('Common', 'Uncommon', 'Rare', 'Very Rare', 'Legendary', 'Artifact').
        cost_gp: Value in gold pieces (integer).
        description: Lore, effects, or magical capabilities.
        damage: Damage die string if applicable (e.g. '1d8+2 slashing', '8d6 fire', or 'n/a').
        properties: List of tags or traits (e.g. ['finesse', 'requires attunement']).

    Returns:
        The created item data and confirmation.
    """
    db = get_firestore_client()
    doc_id = name.lower().replace(" ", "-").replace("'", "")
    doc_ref = db.collection(ITEMS_COLLECTION).document(doc_id)

    item_data = {
        "id": doc_id,
        "name": name,
        "type": item_type.lower(),
        "rarity": rarity,
        "cost_gp": cost_gp,
        "damage": damage,
        "properties": properties or [],
        "description": description,
    }
    doc_ref.set(item_data)
    return {"status": "success", "item": item_data}


def roll_dice(dice: str) -> str:
    """Rolls polyhedral dice for tabletop RPG actions (e.g. '1d20+5', '2d6', 'd20', '8d6').

    Args:
        dice: Standard dice notation like '1d20+3', '2d6', or 'd20'.

    Returns:
        Detailed roll results showing individual rolls and the final total.
    """
    clean_dice = dice.lower().strip().replace(" ", "")
    modifier = 0
    
    if "+" in clean_dice:
        dice_part, mod_part = clean_dice.split("+", 1)
        try:
            modifier = int(mod_part)
        except ValueError:
            return f"Invalid modifier in {dice}"
    elif "-" in clean_dice:
        dice_part, mod_part = clean_dice.split("-", 1)
        try:
            modifier = -int(mod_part)
        except ValueError:
            return f"Invalid modifier in {dice}"
    else:
        dice_part = clean_dice

    if "d" not in dice_part:
        return f"Invalid dice format: {dice}. Expected format like 1d20, 2d6+3."

    parts = dice_part.split("d", 1)
    num_dice = int(parts[0]) if parts[0] else 1
    try:
        sides = int(parts[1])
    except ValueError:
        return f"Invalid dice sides in {dice}"

    if num_dice <= 0 or sides <= 0 or num_dice > 100:
        return "Please roll between 1 and 100 dice with positive sides."

    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    mod_str = f" {'+' if modifier >= 0 else '-'} {abs(modifier)}" if modifier != 0 else ""
    return f"Rolled {dice}: {rolls}{mod_str} = **{total}**"


INVENTORIES_COLLECTION = "character_inventories"


def manage_inventory(
    character_name: str,
    action: str,
    item_id: Optional[str] = None,
    item_name: Optional[str] = None,
    quantity: int = 1,
    gold_change: int = 0,
) -> Dict[str, Any]:
    """Manages a character's inventory and gold balance in Firestore.

    Args:
        character_name: The name of the character (e.g. 'Valeros').
        action: One of 'view' (inspect inventory), 'add' (add items), 'remove' (decrement or remove item), or 'adjust_gold' (add/subtract gold).
        item_id: The identifier of the item (e.g. 'healing-potion', 'vorpal-sword'). Optional for 'view' and 'adjust_gold'.
        item_name: Display name of the item. Optional.
        quantity: Amount of items to add or remove (default 1).
        gold_change: Gold amount to add or subtract (e.g. +50 or -150).

    Returns:
        The updated character inventory summary.
    """
    db = get_firestore_client()
    char_id = character_name.lower().strip().replace(" ", "-")
    doc_ref = db.collection(INVENTORIES_COLLECTION).document(char_id)
    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict()
    else:
        data = {
            "character_name": character_name,
            "gold_gp": 100,
            "items": {},
        }

    action_lower = action.lower().strip()

    if action_lower == "view":
        pass

    elif action_lower == "adjust_gold":
        data["gold_gp"] = max(0, data.get("gold_gp", 0) + gold_change)
        doc_ref.set(data)

    elif action_lower == "add":
        if not item_id:
            return {"error": "item_id is required to add an item."}
        items = data.setdefault("items", {})
        curr = items.get(item_id, {"name": item_name or item_id, "quantity": 0})
        curr["quantity"] += quantity
        if item_name:
            curr["name"] = item_name
        items[item_id] = curr
        if gold_change != 0:
            data["gold_gp"] = max(0, data.get("gold_gp", 0) + gold_change)
        doc_ref.set(data)

    elif action_lower == "remove":
        if not item_id:
            return {"error": "item_id is required to remove an item."}
        items = data.setdefault("items", {})
        if item_id in items:
            items[item_id]["quantity"] -= quantity
            if items[item_id]["quantity"] <= 0:
                del items[item_id]
        if gold_change != 0:
            data["gold_gp"] = max(0, data.get("gold_gp", 0) + gold_change)
        doc_ref.set(data)

    else:
        return {"error": f"Unknown action '{action}'. Valid actions are 'view', 'add', 'remove', 'adjust_gold'."}

    return {
        "character_name": data.get("character_name", character_name),
        "gold_gp": data.get("gold_gp", 0),
        "items": data.get("items", {}),
    }


def search_bestiary(monster_name: str) -> Dict[str, Any]:
    """Queries the free public D&D 5e API for live official monster statistics and abilities.

    Args:
        monster_name: Name of the creature (e.g. 'goblin', 'adult red dragon', 'beholder', 'mimic').

    Returns:
        Monster stats including AC, HP, challenge rating, senses, and attacks/actions.
    """
    slug = monster_name.lower().strip().replace(" ", "-")
    url = f"https://www.dnd5eapi.co/api/2014/monsters/{urllib.parse.quote(slug)}"

    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "RealmMaster-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                actions_summary = [
                    f"{a.get('name')}: {a.get('desc')}"
                    for a in data.get("actions", [])[:4]
                ]
                ac_info = data.get("armor_class", [{}])
                ac_val = ac_info[0].get("value") if ac_info else "n/a"

                return {
                    "name": data.get("name"),
                    "size": data.get("size"),
                    "type": data.get("type"),
                    "alignment": data.get("alignment"),
                    "armor_class": ac_val,
                    "hit_points": data.get("hit_points"),
                    "hit_dice": data.get("hit_dice"),
                    "challenge_rating": data.get("challenge_rating"),
                    "xp": data.get("xp"),
                    "speed": data.get("speed"),
                    "senses": data.get("senses"),
                    "actions": actions_summary,
                }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": f"Monster '{monster_name}' not found in the 5e SRD bestiary archive."}
        return {"error": f"Failed to fetch monster data: HTTP {e.code}"}
    except Exception as e:
        return {"error": f"Public API lookup error: {str(e)}"}


def geocode_address(address: str) -> Dict[str, Any]:
    """Uses the Google Maps Geocoding API to turn an address into latitude and longitude coordinates.

    Args:
        address: The street address, city, landmark, or location query to geocode.

    Returns:
        Dictionary with formatted address, latitude, and longitude.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RealmMaster-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        status = data.get("status")
        if status != "OK" or not data.get("results"):
            return {"error": f"Geocoding failed for '{address}': {status}"}

        first_result = data["results"][0]
        location = first_result.get("geometry", {}).get("location", {})

        return {
            "name": address,
            "address": first_result.get("formatted_address"),
            "location": {
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
            },
        }
    except Exception as e:
        return {"error": f"Geocoding API request failed: {str(e)}"}


def find_nearby_places(
    place_type: str,
    latitude: float,
    longitude: float,
    radius_meters: float = 5000.0,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Uses the Google Maps Places API (New) to find nearby places of a given type.

    Args:
        place_type: Type of place to search for (e.g. 'book_store', 'cafe', 'restaurant', 'park', 'hobby_store').
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        radius_meters: Search radius in meters (default 5000.0, max 50000.0).
        max_results: Maximum number of places to return (default 5, max 20).

    Returns:
        List of found places with name, address, and location coordinates.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    url = "https://places.googleapis.com/v1/places:searchNearby"
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": min(max(1, max_results), 20),
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        "User-Agent": "RealmMaster-Agent/1.0",
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        places = []
        for p in data.get("places", []):
            places.append({
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", "Unknown"),
                "location": {
                    "latitude": p.get("location", {}).get("latitude"),
                    "longitude": p.get("location", {}).get("longitude"),
                },
            })

        return {"places": places, "count": len(places)}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        return {"error": f"Places API request failed (HTTP {e.code}): {err_msg}"}
    except Exception as e:
        return {"error": f"Places API request error: {str(e)}"}


def get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=PROJECT_ID)
    return _storage_client


def get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    return _genai_client


async def generate_item_image(
    prompt: str,
    item_name: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generates an illustration for an item or spell using the gemini-3.1-flash-lite-image model.

    Saves the image to the session artifacts panel and uploads it directly to the public Cloud Storage bucket.

    Args:
        prompt: Detailed visual prompt describing the item appearance, materials, and aura.
        item_name: Name of the item or creature to generate an image for.
        tool_context: ADK ToolContext automatically injected by the runtime.

    Returns:
        Dictionary with public Cloud Storage URL and artifact filename.
    """
    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_part = response.candidates[0].content.parts[0]
        image_bytes = image_part.inline_data.data
        mime_type = image_part.inline_data.mime_type or "image/jpeg"

        # 1. Save artifact in playground's Artifacts panel
        slug = item_name.lower().strip().replace(" ", "_").replace("'", "")
        timestamp = int(time.time())
        filename = f"{slug}_{timestamp}.jpg"

        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename, artifact_part)

        # 2. Upload same bytes directly to public Cloud Storage bucket (without writing local file)
        storage_client = get_storage_client()
        bucket = storage_client.bucket(ASSETS_BUCKET)
        blob = bucket.blob(f"items/{filename}")
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{ASSETS_BUCKET}/items/{filename}"

        return {
            "status": "success",
            "item_name": item_name,
            "artifact_file": filename,
            "public_image_url": public_url,
            "message": f"Image generated for '{item_name}', saved as artifact '{filename}', and published to {public_url}",
        }
    except Exception as e:
        return {"error": f"Failed to generate item image: {str(e)}"}


SANDBOX_RESOURCE = "projects/427977589063/locations/us-east1/reasoningEngines/7352352891077656576/sandboxEnvironments/655915860573028352"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each turn, send the session to Memory Bank for extraction."""
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are RealmMaster, an expert AI Game Master and Tabletop RPG companion. "
        "You help players and Dungeon Masters manage campaigns, roll dice, track character inventories, "
        "explore equipment and spells, look up monsters from the live bestiary, generate visual artwork for items, "
        "locate real-world places (game stores, hobby shops, cafes) using Google Maps, and safely execute Python code in a sandbox. "
        "You remember the user's stated character details, preferences, campaign history, and facts from previous conversations and use them to personalize your responses."
    ),
    workflow_description=(
        "Analyze the request and return structured UI when appropriate. "
        "You have access to tools: `list_items`, `search_item`, `create_or_update_item`, `manage_inventory`, "
        "`search_bestiary`, `generate_item_image`, `geocode_address`, `find_nearby_places`, and `roll_dice`. "
        "Whenever asked to run Python code, calculate probabilities, perform statistical simulations, or analyze numbers, write and execute python code blocks (```python ... ```) to run it directly in your sandbox."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL `generate_item_image` returns after uploading "
        "to the public Cloud Storage bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=SANDBOX_RESOURCE,
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        list_items,
        search_item,
        create_or_update_item,
        manage_inventory,
        search_bestiary,
        generate_item_image,
        geocode_address,
        find_nearby_places,
        roll_dice,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
