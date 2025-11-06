import os
import json
import difflib
from datetime import datetime, timezone
from typing import Optional, Tuple
import aiohttp
import urllib.parse
import commands
import app_commands
from io import BytesIO
from PIL import Image
import asyncio
import re
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service

# =============================
# Configuration and constants
# =============================
VOUCHES_PATH = 'vouches.json'
ARCHIVE_PATH = 'vouch_archive.json'
ITEMS_PATH = 'items.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)

# =============================
# Helpers
# =============================




    """Fetch an image from a URL and return its bytes."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' not in content_type:
                        return None
                    data = await response.read()
                    # Verify image size (Discord avatar size limit: 8MB)
                    if len(data) > 8 * 1024 * 1024:
                        return None
                    # Optionally process image with Pillow
                    try:
                        img = Image.open(BytesIO(data))
                        # Convert to PNG or JPEG if needed
                        output = BytesIO()
                        img.save(output, format='PNG')
                        return output.getvalue()
                    except Exception:
                        return data  # Fallback to raw data if processing fails
                return None
        except Exception as e:
            print(f"Error fetching image from {url}: {e}")
            return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # Corrupted JSON or empty file -> safely return empty
        return {}






# Load items database
def load_items_database():
    """Load and validate items database"""
    try:
        items_file = Path('items.json')
        if not items_file.exists():
            logger.warning("items.json not found, creating dummy database")
            # Create a dummy items.json for testing
            dummy_data = {
                "items": [
                    {
                        "name": "Cute Cowboy",
                        "image": "https://example.com/image.webp",
                        "shards": "250,000 Shards",
                        "coins": "3,000,000 Coins",
                        "usd": "$50.00",
                        "stock": 0,
                        "type": "Capes",
                        "category": "Limited"
                    },
                    {
                        "name": "Antler",
                        "image": "https://example.com/antler.webp",
                        "shards": "5,000 Shards",
                        "coins": "60,000 Coins",
                        "usd": "$1.00",
                        "stock": 100,
                        "type": "Artifacts",
                        "category": "Common"
                    }
                ]
            }
            with open('items.json', 'w', encoding='utf-8') as f:
                json.dump(dummy_data, f, indent=2)
            logger.info("Created dummy items.json")
        
        with open('items.json', 'r', encoding='utf-8') as f:
            items_data = json.load(f)
        
        if 'items' not in items_data:
            raise ValueError("Invalid items.json structure: missing 'items' key")
        
        items_lookup = {}
        for item in items_data['items']:
            if 'name' in item:
                # Create multiple lookup keys for robustness
                name_lower = item['name'].lower().strip()
                items_lookup[name_lower] = item
                # Also store without special characters
                name_clean = re.sub(r'[^\w\s]', '', name_lower)
                items_lookup[name_clean] = item
        
        logger.info(f"Loaded {len(items_lookup)} items from database")
        return items_lookup
    except Exception as e:
        logger.error(f"Error loading items database: {e}")
        return {}

items_lookup = load_items_database()

import subprocess

def check_chromedriver_deps():

    """Check ChromeDriver dependencies"""

    chromedriver_path = Path(__file__).parent / "chromedriver-linux64" / "chromedriver"

    

    try:

        # Try to get dependency info

        result = subprocess.run(

            ['ldd', str(chromedriver_path)],

            capture_output=True,

            text=True

        )

        logger.info(f"ChromeDriver dependencies:\n{result.stdout}")

        logger.error(f"Missing dependencies:\n{result.stderr}")

    except Exception as e:

        logger.error(f"Could not check dependencies: {e}")

# Call before setup_driver()

check_chromedriver_deps()

def setup_driver():
    """Setup headless Chrome driver with portable Chrome"""
    import os
    from pathlib import Path
    
    # Get paths relative to bot.py
    base_dir = Path(__file__).parent.absolute()
    chrome_binary = base_dir / "chrome-linux64" / "chrome"
    chromedriver_binary = base_dir / "chromedriver-linux64" / "chromedriver"
    
    # Make executables if not already
    if chrome_binary.exists():
        os.chmod(chrome_binary, 0o755)
    if chromedriver_binary.exists():
        os.chmod(chromedriver_binary, 0o755)
    
    chrome_options = Options()
    chrome_options.binary_location = str(chrome_binary)
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.page_load_strategy = 'eager'
    
    try:
        service = Service(executable_path=str(chromedriver_binary))
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(5)
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
        logger.error(f"Chrome binary: {chrome_binary} (exists: {chrome_binary.exists()})")
        logger.error(f"ChromeDriver binary: {chromedriver_binary} (exists: {chromedriver_binary.exists()})")
        raise

def parse_currency(value_str):
    """Parse currency string to float with robust handling"""
    if not value_str or value_str == 'N/A' or value_str == '':
        return 0.0
    
    try:
        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r'[^\d.]', '', str(value_str))
        return float(cleaned) if cleaned else 0.0
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse currency '{value_str}': {e}")
        return 0.0

def find_item_in_database(item_name, items_lookup):
    """Find item in database with fuzzy matching"""
    item_name_lower = item_name.lower().strip()
    
    # Direct match
    if item_name_lower in items_lookup:
        return items_lookup[item_name_lower]
    
    # Clean match (without special characters)
    item_name_clean = re.sub(r'[^\w\s]', '', item_name_lower)
    if item_name_clean in items_lookup:
        return items_lookup[item_name_clean]
    
    # Partial match disabled - too risky for false positives
    # Only do partial matching if the name is at least 80% similar
    for key, value in items_lookup.items():
        if len(item_name_clean) > 4 and len(key) > 4:
            # Check if one is substantially contained in the other (at least 80% overlap)
            shorter = min(len(item_name_clean), len(key))
            longer = max(len(item_name_clean), len(key))
            if shorter / longer >= 0.8:
                if item_name_clean in key or key in item_name_clean:
                    logger.info(f"Fuzzy matched '{item_name}' to '{value.get('name', key)}'")
                    return value
    
    return None

def safe_click(driver, element, max_retries=3):
    """Safely click an element with retries"""
    for attempt in range(max_retries):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", element)
            return True
        except StaleElementReferenceException:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Click attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(0.5)
    return False

def scrape_inventory(ign):
    """Scrape inventory from zeqa.net profile with robust error handling"""
    driver = None
    
    try:
        driver = setup_driver()
        url = f"https://app.zeqa.net/profile?player={ign}"
        
        logger.info(f"Starting inventory scrape for {ign}")
        driver.get(url)
        
        # Wait for page to load completely
        wait = WebDriverWait(driver, 20)
        
        # Wait for body to be present
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        
        # Check if profile exists (look for error messages)
        try:
            error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'not found') or contains(text(), 'does not exist')]")
            if error_elements:
                raise Exception("Player profile not found")
        except:
            pass
        
        # Scroll to cosmetic collection section
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4);")
        time.sleep(2)
        
        # Find all category sections with multiple attempts
        all_categories = []
        for attempt in range(3):
            try:
                all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                if all_categories:
                    break
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} to find categories failed: {e}")
                if attempt == 2:
                    raise
        
        if not all_categories:
            raise Exception("No cosmetic categories found on profile")
        
        logger.info(f"Found {len(all_categories)} total categories")
        
        # Filter to only main cosmetic type categories
        valid_category_names = ["Artifact", "Cape", "Killphrase", "Projectile", "Mount"]
        main_categories = []
        
        for category in all_categories:
            try:
                category_header = category.find_element(By.TAG_NAME, "h6")
                category_name = category_header.text.strip()
                if category_name in valid_category_names:
                    main_categories.append((category, category_name))
                    logger.info(f"Found main category: {category_name}")
            except:
                continue
        
        logger.info(f"Processing {len(main_categories)} main categories")
        
        owned_items = []
        total_usd = 0.0
        total_coins = 0.0
        total_shards = 0.0
        categories_processed = 0
        
        for category_tuple in main_categories:
            try:
                category, category_name = category_tuple
                
                # Re-locate the category in the current page state
                all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                category = None
                for cat in all_categories:
                    try:
                        header = cat.find_element(By.TAG_NAME, "h6")
                        if header.text.strip() == category_name:
                            category = cat
                            break
                    except:
                        continue
                
                if not category:
                    logger.warning(f"Could not relocate category: {category_name}")
                    continue
                
                # Get the count (n/total format)
                try:
                    count_elements = category.find_elements(By.TAG_NAME, "h3")
                    count_text = ""
                    for elem in count_elements:
                        text = elem.text.strip()
                        if text and '/' in text:
                            count_text = text
                            break
                    
                    if not count_text:
                        logger.info(f"No count found for {category_name}, skipping")
                        continue
                except Exception as e:
                    logger.warning(f"Error getting count for {category_name}: {e}")
                    continue
                
                # Parse the count (e.g., "5/295" or "[5/295]" -> owned = 5)
                match = re.match(r'\[?(\d+)/(\d+)\]?', count_text)
                if not match:
                    logger.warning(f"Invalid count format for {category_name}: {count_text}")
                    continue

                owned_count = int(match.group(1))
                total_count = int(match.group(2))

                # Skip if no items owned
                if owned_count == 0:
                    logger.info(f"Skipping {category_name}: 0/{total_count} items")
                    continue

                logger.info(f"Processing {category_name}: {owned_count}/{total_count} items")
                
                # Click on the category to expand it
                dropdown_toggle = category.find_element(By.CSS_SELECTOR, ".black-dropdown-toggle")
                safe_click(driver, dropdown_toggle)
                time.sleep(1.5)
                
                # Find and interact with filter dropdown
                try:
                    # Re-find category after clicking
                    all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                    category = None
                    for cat in all_categories:
                        try:
                            header = cat.find_element(By.TAG_NAME, "h6")
                            if header.text.strip() == category_name:
                                category = cat
                                break
                        except:
                            continue
                    
                    if not category:
                        logger.warning(f"Could not relocate category after expand: {category_name}")
                        continue
                    
                    filter_dropdown = category.find_element(By.CSS_SELECTOR, ".dropdown.zeqa-dropdown select")
                    select = Select(filter_dropdown)
                    
                    # Try different variations of "Show Owned"
                    selected = False
                    for option_text in ["Show Owned", "Owned", "show owned"]:
                        try:
                            select.select_by_visible_text(option_text)
                            selected = True
                            break
                        except:
                            continue
                    
                    if not selected:
                        # Try by value
                        for option in select.options:
                            if 'owned' in option.text.lower():
                                select.select_by_visible_text(option.text)
                                selected = True
                                break
                    
                    if not selected:
                        logger.warning(f"Could not select 'Show Owned' for {category_name}")
                        continue
                    
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error selecting filter for {category_name}: {e}")
                    continue
                
                # Get all cosmetic items with retry logic
                cosmetic_items = []
                for attempt in range(3):
                    try:
                        all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                        category = None
                        for cat in all_categories:
                            try:
                                header = cat.find_element(By.TAG_NAME, "h6")
                                if header.text.strip() == category_name:
                                    category = cat
                                    break
                            except:
                                continue
                        
                        if category:
                            cosmetic_items = category.find_elements(By.CSS_SELECTOR, ".oreuidiv")
                        if cosmetic_items:
                            break
                        time.sleep(1)
                    except:
                        if attempt == 2:
                            logger.error(f"Failed to find items in {category_name}")
                
                logger.info(f"Found {len(cosmetic_items)} items in {category_name}")
                
                for item_element in cosmetic_items:
                    try:
                        # Get item name with multiple selector attempts
                        item_name = None
                        try:
                            item_name_elem = item_element.find_element(By.CSS_SELECTOR, ".oreuitextblock.cosmetics")
                            item_name = item_name_elem.text.strip()
                        except:
                            try:
                                item_name_elem = item_element.find_element(By.CSS_SELECTOR, ".oreuitextblock")
                                item_name = item_name_elem.text.strip()
                            except:
                                logger.warning("Could not extract item name")
                                continue
                        
                        if not item_name:
                            continue
                        
                        # Look up item in database
                        item_data = find_item_in_database(item_name, items_lookup)
                        
                        if item_data:
                            # Parse values
                            usd_value = parse_currency(item_data.get('usd', '0'))
                            coins_value = parse_currency(item_data.get('coins', '0'))
                            shards_value = parse_currency(item_data.get('shards', '0'))
                            
                            total_usd += usd_value
                            total_coins += coins_value
                            total_shards += shards_value
                            
                            owned_items.append({
                                'name': item_name,
                                'category': category_name,
                                'usd': usd_value,
                                'coins': coins_value,
                                'shards': shards_value
                            })
                            
                            logger.info(f"  ✓ {item_name}: ${usd_value:,.2f}")
                        else:
                            logger.warning(f"   {item_name}: NOT FOUND in database")
                            
                    except Exception as e:
                        logger.error(f"Error processing item: {e}")
                        continue
                
                categories_processed += 1
                
                # Collapse the category
                try:
                    all_categories = driver.find_elements(By.CSS_SELECTOR, ".black-dropdown.black-zeqa-dropdown")
                    category = None
                    for cat in all_categories:
                        try:
                            header = cat.find_element(By.TAG_NAME, "h6")
                            if header.text.strip() == category_name:
                                category = cat
                                break
                        except:
                            continue
                    
                    if category:
                        dropdown_toggle = category.find_element(By.CSS_SELECTOR, ".black-dropdown-toggle")
                        safe_click(driver, dropdown_toggle)
                        time.sleep(0.8)
                except:
                    pass  # Non-critical if collapse fails
                
            except Exception as e:
                logger.error(f"Error processing category {category_name}: {e}")
                continue
        
        logger.info(f"Scraping complete: {len(owned_items)} items from {categories_processed} categories")
        
        return {
            'success': True,
            'ign': ign,
            'items': owned_items,
            'total_usd': total_usd,
            'total_coins': total_coins,
            'total_shards': total_shards,
            'item_count': len(owned_items),
            'categories_processed': categories_processed
        }
        
    except Exception as e:
        logger.error(f"Fatal error scraping inventory for {ign}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'ign': ign
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

active_evaluations = set()



# =============================
# Bot setup
# =============================

intents.message_content = True
intents.guilds = True
intents.members = True




    embed = discord.Embed(
        title='New Vouch',
        color=0x00FF7F,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=f"{buyer} vouched", icon_url=buyer.display_avatar.url if buyer.display_avatar else None)
    embed.set_thumbnail(url=seller.display_avatar.url if seller.display_avatar else None)
    embed.add_field(name='Seller', value=seller.mention)
    embed.add_field(name='Buyer', value=buyer.mention)
    embed.add_field(name='Item', value=_clamp(item, 120), inline=False)
    embed.add_field(name='Reason', value=_clamp(reason, 512), inline=False)
    if proof_url:
        embed.add_field(name='Proof', value=proof_url, inline=False)
    embed.add_field(name='Vouch ID', value=vouch_id)
    embed.set_footer(text=f"Total: {total_for_seller}")
    return embed


# =============================
# Events
# =============================


    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        run_app()
        print("Admin panel and API started.")
        print('Admin panel running at http://zeqamart.duckdns.org:8000/panel')
        print('API running at http://zeqamart.duckdns.org:8000/api')
    except Exception as e:
        print(f'Failed to start admin panel: {e}')
    #try:
        #run_admin_panel()
      #  print('Admin panel running at http://zmpanel.duckdns.org:8000')
  #  except Exception as e:
        #print(f'Failed to start admin panel: {e}')
    #try:
      #  #run_api()
      #  #print('API running at http://zeqamartapi.duckdns.org:8003')
   # except Exception as e:
       # print(f'Failed to start API: {e}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} global commands: {[c.name for c in synced]}')
    except Exception as e:
        print(f'Error syncing commands: {e}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Zeqa trades"))


# =============================
# Error handling for slash commands
# =============================


    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f'This command is on cooldown. Try again in {error.retry_after:.1f}s.'
        )
        return
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message('You lack permissions for this action.', ephemeral=True)
        return
    if isinstance(error, app_commands.BotMissingPermissions):
        await interaction.response.send_message('I lack required permissions to do that.', ephemeral=True)
        return
    try:
        await interaction.response.send_message('An error occurred while processing your command.')
    except discord.InteractionResponded:
        await interaction.followup.send('An error occurred while processing your command.')
    # Log to console
    print(f"Error in command {interaction.command.name if interaction.command else 'unknown'}: {error}")


# =============================
# Commands
# =============================
@app_commands.describe(
    seller='The seller you are vouching for',
    item='Item or service received',
    reason='Brief reason for the vouch (optional)',
    proof='Optional file/screenshot as proof'
)
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)


    interaction: discord.Interaction,
    seller: discord.User,
    item: str,
    reason: Optional[str] = None,
    proof: Optional[discord.Attachment] = None,
):
    voucher = interaction.user
    reason = reason or ''
    if seller.id == voucher.id:
        await interaction.response.send_message('You cannot vouch for yourself.', ephemeral=True)
        return

    vouches = _safe_load_json(VOUCHES_PATH)
    now = datetime.now(timezone.utc).isoformat()
    vouch_id = _generate_vouch_id(vouches)

    # Duplicate check (one vouch per buyer per seller)
    data = vouches.get(str(seller.id))
    if data:
        for v in data.get('vouches', []):
            if v.get('from') == str(voucher.id):
                await interaction.response.send_message('You have already vouched for this seller.', ephemeral=True)
                return
    else:
        vouches[str(seller.id)] = {'vouches': [], 'total': 0}

    proof_url = None
    if proof is not None:
        # Accept only images up to ~8 MB or any attachment URL
        proof_url = proof.url

    vouches[str(seller.id)]['vouches'].append(
        {
            'id': vouch_id,
            'from': str(voucher.id),
            'item': item,
            'reason': reason,
            'timestamp': now,
            'proof_url': proof_url,
        }
    )
    vouches[str(seller.id)]['total'] = len(vouches[str(seller.id)]['vouches'])

    _safe_save_json(VOUCHES_PATH, vouches)

    embed = _build_vouch_embed(
        seller=seller,
        buyer=voucher,
        item=item,
        reason=reason,
        vouch_id=vouch_id,
        total_for_seller=vouches[str(seller.id)]['total'],
        proof_url=proof_url,
    )

    await interaction.response.send_message(embed=embed)


@app_commands.describe(
    seller="Seller to view", page="Page number (5 vouches per page)"
)


    vouches = _safe_load_json(VOUCHES_PATH)
    data = vouches.get(str(seller.id))
    if not data or not data.get('vouches'):
        await interaction.response.send_message('No vouches found for this seller.')
        return

    per_page = 5
    total = data['total']
    items = data['vouches']

    # Pagination
    max_page = max(1, (len(items) + per_page - 1) // per_page)
    page = max(1, min(page, max_page))
    start = (page - 1) * per_page
    end = start + per_page

    embed = discord.Embed(
        title=f"{seller.name}'s Vouches",
        color=0x3498DB,
        timestamp=datetime.now(timezone.utc),
        description=f"Total: **{total}**\nPage {page}/{max_page}",
    )
    embed.set_thumbnail(url=seller.display_avatar.url if seller.display_avatar else None)

    for v in items[::-1][start:end]:
        buyer_tag = f"<@{v.get('from')}>"
        reason = _clamp(v.get('reason', ''), 256)
        item_name = _clamp(v.get('item', ''), 120)
        ts = v.get('timestamp', 'N/A')
        vid = v.get('id', 'N/A')
        proof = v.get('proof_url')
        value = f"Item: {item_name}\nReason: {reason}\nDate: {ts}\nID: `{vid}`"
        if proof:
            value += f"\nProof: {proof}"
        embed.add_field(name=f"Buyer: {buyer_tag}", value=value, inline=False)

    await interaction.response.send_message(embed=embed)


@app_commands.describe(vouch_id='The vouch ID to remove (you must be the voucher)')


    vouches = _safe_load_json(VOUCHES_PATH)
    found = _find_vouch(vouches, vouch_id)
    if not found:
        await interaction.response.send_message('Vouch ID not found.', ephemeral=True)
        return

    seller_id, idx, vobj = found
    if vobj.get('from') != str(interaction.user.id):
        await interaction.response.send_message('You can only remove vouches you created.', ephemeral=True)
        return

    # Remove and archive
    removed = vouches[seller_id]['vouches'].pop(idx)
    vouches[seller_id]['total'] = len(vouches[seller_id]['vouches'])
    _safe_save_json(VOUCHES_PATH, vouches)

    archive = _safe_load_json(ARCHIVE_PATH)
    archive_id = f"ARCH-{int(datetime.now(timezone.utc).timestamp())}"
    archive[archive_id] = {
        'action': 'unvouch',
        'seller': seller_id,
        'vouch': removed,
        'by': str(interaction.user.id),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    _safe_save_json(ARCHIVE_PATH, archive)

    try:
        seller_user = await interaction.client.fetch_user(int(seller_id))
    except Exception:
        seller_user = discord.Object(id=int(seller_id))  # fallback mention

    embed = discord.Embed(
        title='Vouch Removed',
        color=0xE74C3C,
        timestamp=datetime.now(timezone.utc),
        description=f"Removed vouch `{vouch_id}` for {getattr(seller_user, 'mention', f'<@{seller_id}>')}.",
    )
    await interaction.response.send_message(embed=embed)


@app_commands.describe(limit='How many sellers to show (top by vouch count)')


    limit = max(1, min(limit, 25))
    vouches = _safe_load_json(VOUCHES_PATH)
    ranking = sorted(
        ((sid, data.get('total', 0)) for sid, data in vouches.items()), key=lambda x: x[1], reverse=True
    )[:limit]

    embed = discord.Embed(
        title='Top Sellers Leaderboard',
        color=0xF1C40F,
        timestamp=datetime.now(timezone.utc),
    )

    if not ranking:
        embed.description = 'No vouches recorded yet.'
        await interaction.response.send_message(embed=embed)
        return

    lines = []
    for rank, (sid, total) in enumerate(ranking, start=1):
        lines.append(f"#{rank} - <@{sid}> • {total} vouches")

    embed.description = "\n".join(lines)
    await interaction.response.send_message(embed=embed)




    vouches = _safe_load_json(VOUCHES_PATH)
    mine = []
    for data in vouches.values():
        for v in data.get('vouches', []):
            if v.get('from') == str(interaction.user.id):
                mine.append((data, v))

    if not mine:
        await interaction.response.send_message('You have not vouched for anyone yet.')
        return

    embed = discord.Embed(
        title=f"{interaction.user.name}'s recent vouches",
        color=0x2ECC71,
        timestamp=datetime.now(timezone.utc),
    )

    for _, v in mine[-5:][::-1]:
        vid = v.get('id', 'N/A')
        ts = v.get('timestamp', 'N/A')
        item_name = _clamp(v.get('item', ''), 120)
        reason = _clamp(v.get('reason', ''), 256)
        embed.add_field(
            name=f"ID: {vid}",
            value=f"Item: {item_name}\nReason: {reason}\nDate: {ts}",
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@app_commands.describe(vouch_id='The vouch ID to look up')


    vouches = _safe_load_json(VOUCHES_PATH)
    found = _find_vouch(vouches, vouch_id)
    if not found:
        await interaction.response.send_message('Vouch ID not found.', ephemeral=True)
        return

    seller_id, _idx, v = found
    try:
        seller_user = await interaction.client.fetch_user(int(seller_id))
    except Exception:
        seller_user = None

    buyer_user = None
    try:
        buyer_user = await interaction.client.fetch_user(int(v.get('from', 0)))
    except Exception:
        buyer_user = None

    embed = discord.Embed(
        title='Vouch Information',
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name='Vouch ID', value=vouch_id, inline=False)
    if seller_user:
        embed.add_field(name='Seller', value=seller_user.mention)
    else:
        embed.add_field(name='Seller', value=f"<@{seller_id}>")
    if buyer_user:
        embed.add_field(name='Buyer', value=buyer_user.mention)
    else:
        embed.add_field(name='Buyer', value=f"<@{v.get('from', 'unknown')}>")

    embed.add_field(name='Item', value=_clamp(v.get('item', ''), 120), inline=False)
    embed.add_field(name='Reason', value=_clamp(v.get('reason', ''), 512), inline=False)
    ts = v.get('timestamp', 'N/A')
    embed.add_field(name='Date', value=ts)
    proof = v.get('proof_url')
    if proof:
        embed.add_field(name='Proof', value=proof, inline=False)

    await interaction.response.send_message(embed=embed)


@app_commands.describe(cosmetic='Cosmetic name (case-insensitive)')


    raw = _safe_load_json(ITEMS_PATH)
    if not raw:
        await interaction.response.send_message('No stock data available.')
        return

    # Extract {name: stock} from {"items": [...]}
    data = {}
    for item in raw.get('items', []):
        if isinstance(item, dict) and 'name' in item:
            name = str(item['name'])
            val = item.get('stock', 0)
            try:
                val = int(val)
            except Exception:
                val = 0
            data[name] = val

    if not data:
        await interaction.response.send_message('No stock data available.')
        return

    # Normalize names: trim, lower, keep alphanumerics only
    query = cosmetic or ''
    key_map = {_norm(k): k for k in data.keys()}
    key = key_map.get(_norm(query))

    if key is None:
        # Try substring suggestions using stripped/lowered comparison
        ql = query.strip().lower()
        candidates = [k for k in data.keys() if ql in k.lower()]
        if not candidates:
            # Fallback to fuzzy matches
            candidates = difflib.get_close_matches(query, list(data.keys()), n=3, cutoff=0.5)
        if not candidates:
            await interaction.response.send_message(f'Cosmetic "{cosmetic}" not found.')
            return
        suggestions = ", ".join(candidates)
        await interaction.response.send_message(
            f'Cosmetic "{cosmetic}" not found. Did you mean: {suggestions}?'
        )
        return

    stock_val = data.get(key, 0)
    # Normalize possible string numbers
    try:
        stock_val = int(stock_val)
    except Exception:
        pass

    embed = discord.Embed(
        title='Cosmetic Stock',
        color=0x00e676,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name='Cosmetic', value=key, inline=True)
    embed.add_field(name='Stock', value=str(stock_val), inline=True)

    await interaction.response.send_message(embed=embed)
    
@app_commands.describe(item='Item name (case-insensitive)')


    # Defer immediately to prevent timeout
    await interaction.response.defer()
    
    raw = _safe_load_json(ITEMS_PATH)
    raw = raw.get('items', [])
    if not raw or not isinstance(raw, list):
        await interaction.followup.send('No item pricing data available.')
        return

    key_map = {_norm(entry.get('name', '')): entry for entry in raw if isinstance(entry, dict)}
    entry = key_map.get(_norm(item))

    if entry is None:
        ql = (item or '').strip().lower()
        names = [e.get('name', '') for e in raw if isinstance(e, dict)]
        candidates = [n for n in names if ql in n.lower()]
        if not candidates:
            candidates = difflib.get_close_matches(item, names, n=3, cutoff=0.5)
        print(f"No match for '{item}'. Suggestions: {candidates}")
        if not candidates:
            await interaction.followup.send(f'Item "{item}" not found.')
            return
        await interaction.followup.send(
            f'Item "{item}" not found. Did you mean: {", ".join(candidates)}?'
        )
        return

    name = entry.get('name', item)
    shards = entry.get('shards', 'N/A')
    coins = entry.get('coins', 'N/A')
    usd = entry.get('usd', 'N/A')
    item_type = entry.get('type', 'Unknown')
    category = entry.get('category', 'Unknown')
    item_id = entry.get('id', 'N/A')
    existing_items = entry.get('existingItems', 'N/A')


    # Get color from item data or use default based on category
    color_hex = entry.get('color')
    if not color_hex:
        category_lower = category.lower()
        if 'common' in category_lower:
            color_hex = '008006'
        elif 'rare' in category_lower:
            color_hex = '203487'
        elif 'epic' in category_lower:
            color_hex = 'D12CB8'
        elif 'legendary' in category_lower:
            color_hex = 'E89013'
        elif 'limited' in category_lower:
            color_hex = 'BA0D0D'
        elif 'exotic' in category_lower:
            color_hex = '2DB7CC'
        elif 'partner' in category_lower:
            color_hex = '431E87'
        else:
            color_hex = 'FFFFFF'
    
    try:
        color = int(color_hex.lstrip('#'), 16)
    except (ValueError, TypeError):
        color = 0xFFFFFF
    
    embed = discord.Embed(
        title=f"{name}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(name='📦 Type', value=item_type, inline=True)
    embed.add_field(name='🧪 Category', value=category, inline=True)
    embed.add_field(name='<:emoji_1:1422120591724384296> Shards', value=str(shards), inline=False)
    embed.add_field(name='<:emoji_1:1422120631771856956> Coins', value=str(coins), inline=False)
    embed.add_field(name='💵 USD', value=str(usd), inline=False)
    embed.add_field(name='🆔 ID', value=str(item_id), inline=True)
    embed.add_field(name='🧮 Existing Items', value=str(existing_items), inline=True)


    # Try to fetch image with timeout
    try:
        image_url = f"https://zeqamart.onrender.com/api/download-image/{urllib.parse.quote(name)}"
        
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    file = discord.File(BytesIO(image_data), filename="item.png")
                    embed.set_thumbnail(url="attachment://item.png")
                    await interaction.followup.send(embed=embed, file=file)
                    return
                else:
                    print(f"Image download failed: HTTP {response.status}")
                
    except asyncio.TimeoutError:
        print(f"Timeout downloading image for {name}")
    except Exception as e:
        print(f"Error downloading image: {e}")
    
    # Fallback: send without image
    await interaction.followup.send(embed=embed)
    
# ===== Staff utilities =====


    
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message('Only the requester can confirm this action.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Confirm reset', style=discord.ButtonStyle.danger)
    
        # Perform reset
        vouches = _safe_load_json(VOUCHES_PATH)
        data = vouches.get(str(self.seller.id))
        if not data or not data.get('vouches'):
            await interaction.response.send_message('No vouches to reset.', ephemeral=True)
            self.stop()
            return

        archive = _safe_load_json(ARCHIVE_PATH)
        archive_id = f"ARCH-{int(datetime.now(timezone.utc).timestamp())}"
        archive[archive_id] = {
            'action': 'reset',
            'seller': str(self.seller.id),
            'vouches': data['vouches'],
            'staff': str(interaction.user.id),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        _safe_save_json(ARCHIVE_PATH, archive)

        del vouches[str(self.seller.id)]
        _safe_save_json(VOUCHES_PATH, vouches)

        embed = discord.Embed(
            title='Vouch Reset',
            color=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name='Seller', value=self.seller.mention)
        embed.add_field(name='Staff', value=interaction.user.mention)
        embed.add_field(name='Archive ID', value=archive_id)

        await interaction.response.edit_message(content='Vouches reset.', view=None, embed=embed)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary)
    
        await interaction.response.edit_message(content='Reset cancelled.', view=None)
        self.stop()

# Rate conversion command
@app_commands.describe(
    amount='Amount to convert',
    from_unit='Unit to convert from: coins, shards, usd',
    to_unit='Unit to convert to: coins, shards, usd'
)


    # Conversion rates
    rates = {
        'coins_to_usd': 0.0000166667,  # 1 coin = 0.0000166667 USD (1 USD = 60,000 coins)
        'coins_to_shards': 0.0833333,  # 1 coin = 0.0833333 shards (1 shard = 12 coins)
        'shards_to_usd': 0.0002,       # 1 shard = 0.0002 USD (1 USD = 5,000 shards)
        'shards_to_coins': 12,         # 1 shard = 12 coins
        'usd_to_coins': 60000,         # 1 USD = 60,000 coins
        'usd_to_shards': 5000,         # 1 USD = 5,000 shards
    }

    from_unit = from_unit.lower()
    to_unit = to_unit.lower()
    valid_units = ['coins', 'shards', 'usd']
    if from_unit not in valid_units or to_unit not in valid_units:
        await interaction.response.send_message('Units must be one of: coins, shards, usd')
        return

    result = None
    # Convert input to USD first, then to target
    if from_unit == to_unit:
        result = amount
    elif from_unit == 'coins':
        if to_unit == 'usd':
            result = amount * rates['coins_to_usd']
        elif to_unit == 'shards':
            result = amount * rates['coins_to_shards']
    elif from_unit == 'shards':
        if to_unit == 'usd':
            result = amount * rates['shards_to_usd']
        elif to_unit == 'coins':
            result = amount * rates['shards_to_coins']
    elif from_unit == 'usd':
        if to_unit == 'coins':
            result = amount * rates['usd_to_coins']
        elif to_unit == 'shards':
            result = amount * rates['usd_to_shards']

    if result is None:
        await interaction.response.send_message('Conversion not supported.')
        return

    # Emoji mapping
    emoji_map = {'coins': '<:emoji_1:1422120631771856956>', 'shards': '<:emoji_1:1422120591724384296>', 'usd': '💵'}
    
    embed = discord.Embed(
    title="Currency Conversion Result",
    description=f"{emoji_map.get(from_unit, '')} **{amount:,} {from_unit.upper()}** = {emoji_map.get(to_unit, '')} **{result:,.2f} {to_unit.upper()}**",
    color=discord.Color.green()
)
    await interaction.response.send_message(embed=embed)


# Inventory Command
# Replace your entire inventory command (around line 515) with this updated version


@app_commands.describe(ign="In-game name of the player")

    """Check player inventory worth"""
    
    # Sanitize IGN
    ign = ign.strip()
    if not ign or len(ign) > 32:
        error_embed = discord.Embed(
            title="Invalid Input",
            description="Please provide a valid in-game name (1-32 characters).",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return
    
    # Check if already evaluating this player
    if ign.lower() in active_evaluations:
        await interaction.response.send_message(
            f"An evaluation for `{ign}` is already in progress. Please wait.",
            ephemeral=True
        )
        return
    
    active_evaluations.add(ign.lower())
   
    # Track start time
    start_time = time.time()
    
    try:
        loading_embed = discord.Embed(
            title="Inventory Evaluation in Progress",
            description=(
                f"**Player:** `{ign}`\n\n"
                "MartBot is currently performing a detailed evaluation of this players inventory."
                "Each cosmetic is **individually analyzed**, matched against the database, "
                "and its worth is calculated in shards, coins, and USD.\n\n"
                "This process involves multiple validation steps to ensure precision:\n"
                "• Accessing the player profile securely\n"
                "• Identifying each cosmetic\n" 
                "• Matching cosmetics against the internal item database\n"
                "• Computing total valuation across all supported currencies\n\n"
                "Because this process is performed manually by MartBot" 
                "it may take a bit of time to complete depending on the connection speed.\n\n" 
                "**Please be patient** while the evaluation is underway."
            ),
            color=0x5865F2
        )
        loading_embed.set_footer(text="Powered by MartBot") 
        
        # Defer with the loading embed
        await interaction.response.send_message(embed=loading_embed)
        
        # Run the scraping in a separate thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, scrape_inventory, ign)
        
        if not result['success']:
            error_embed = discord.Embed(
                title="Evaluation Failed",
                description=(
                    f"Failed to evaluate inventory for `{ign}`.\n\n"
                    f"**Error:** {result.get('error', 'Unknown error')}\n\n"
                    "This could be due to:\n"
                    "• Invalid player name\n"
                    "• Profile not found\n"
                    "• Network connectivity issues\n"
                    "• Website temporarily unavailable"
                ),
                color=discord.Color.red()
            )
            error_embed.set_footer(text="Please verify the player name and try again")
            await interaction.edit_original_response(embed=error_embed)
            return
        
        # Calculate type counts
        type_counts = {}
        for item in result['items']:
            item_name = item['name']
            item_data = find_item_in_database(item_name, items_lookup)
            if item_data and 'type' in item_data:
                item_type = item_data['type']
                type_counts[item_type] = type_counts.get(item_type, 0) + 1
        
        # Create result embed
        result_embed = discord.Embed(
            title=f"Inventory Worth - {result['ign']}",
            color=discord.Color.green()
        )
        
        # Add total values with custom emojis
        result_embed.add_field(
            name="Total USD Value",
            value=f"**${result['total_usd']:,.2f}**",
            inline=True
        )
        result_embed.add_field(
            name="Total Coins",
            value=f"<:emoji_1:1422120631771856956> **{result['total_coins']:,.0f}**",
            inline=True
        )
        result_embed.add_field(
            name="Total Shards",
            value=f"<:emoji_1:1422120591724384296> **{result['total_shards']:,.0f}**",
            inline=True
        )
        
        # Add type breakdown
        if type_counts:
            type_text = ""
            # Sort by count descending
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            for item_type, count in sorted_types:
                type_text += f"**{item_type}:** {count}\n"
            
            result_embed.add_field(
                name="Cosmetic Types",
                value=type_text[:1024],
                inline=False
            )
        
        # Add item count and categories
        result_embed.add_field(
            name="Total Items",
            value=f"**{result['item_count']}** cosmetics",
            inline=False
        )
        
        # Add most valuable items (top 10) - sort by coins, show all items
        # Replace the "Most Valuable Items" section (around line 575-590) with this:

        # Add most valuable items (top 10) - sort by coins, show all items
        if result['items']:
            # Sort by coins value (highest first)
            top_items = sorted(result['items'], key=lambda x: x['coins'], reverse=True)[:10]
            
            if top_items:
                items_text = ""
                items_added = 0
                
                for i, item in enumerate(top_items, 1):
                    # Get item type from database
                    item_data = find_item_in_database(item['name'], items_lookup)
                    item_type = item_data.get('type', 'Unknown') if item_data else 'Unknown'
                    
                    # Build the item entry
                    item_entry = f"{i}. **{item['name']}** [{item_type}]\n"
                    item_entry += f"\u200b     <:emoji_1:1422120631771856956> {item['coins']:,.0f} • <:emoji_1:1422120591724384296> {item['shards']:,.0f}\n\n"
                    
                    # Check if adding this item would exceed the limit
                    if len(items_text) + len(item_entry) > 1020:  # Leave buffer for safety
                        break
                    
                    items_text += item_entry
                    items_added += 1
                
                result_embed.add_field(
                    name=f"Most Valuable Items",
                    value=items_text.rstrip(),  # Remove trailing whitespace
                    inline=False
                )
        
        result_embed.set_footer(text=f"Evaluated by Martbot • {result['item_count']} items analyzed")
        result_embed.timestamp = discord.utils.utcnow()
        
        await interaction.edit_original_response(embed=result_embed)
        
    finally:
        # Remove from active evaluations
        active_evaluations.discard(ign.lower())

# Reset vouch command
@app_commands.checks.has_permissions(manage_guild=True)


    vouches = _safe_load_json(VOUCHES_PATH)
    data = vouches.get(str(seller.id))
    total = data.get('total', 0) if data else 0

    view = ConfirmResetView(requester_id=interaction.user.id, seller=seller)
    await interaction.response.send_message(
        f'Confirm resetting {total} vouch(es) for {seller.mention}?',
        view=view,
        ephemeral=True,
    )


# =============================
# Startup
# =============================
if __name__ == '__main__':
    token = "MTQyMTkwMTU3ODE5MzA4MDUzMw.GqM9Ze.P46_QftChN5Du5eLVQ24padjNj1IzPyb_idb20"
    if not token:
        raise ValueError('Set DISCORD_TOKEN environment variable')
    bot.run(token)


from fastapi import FastAPI
import uvicorn, os

app = FastAPI()

@app.get("/inventory/{ign}")
def get_inventory(ign: str):
    return scrape_inventory(ign)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("render_scraper:app", host="0.0.0.0", port=port)
