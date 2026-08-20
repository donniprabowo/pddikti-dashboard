import re
import time
import os
import logging
from DrissionPage import ChromiumPage, ChromiumOptions

logger = logging.getLogger(__name__)

def update_config_file(new_cf_clearance):
    """Mengupdate file config.py dengan CF_CLEARANCE yang baru."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Regex untuk mengganti nilai CF_CLEARANCE
    new_content = re.sub(r'CF_CLEARANCE\s*=\s*[\'"].*?[\'"]', f'CF_CLEARANCE = "{new_cf_clearance}"', content)
    
    with open(config_path, 'w') as f:
        f.write(new_content)

def get_fresh_clearance():
    """Membuka Chrome siluman, bypass Turnstile, dan ekstrak cf_clearance."""
    try:
        co = ChromiumOptions().auto_port()
        # co.headless() # Jika CF galak, lebih baik jangan di-hide
        
        page = ChromiumPage(co)
        page.get('https://pddikti.kemdiktisaintek.go.id/')
        
        # Tunggu sampai title bukan 'Just a moment...'
        success = False
        for i in range(15):
            if 'Just a moment' not in page.title:
                success = True
                break
            time.sleep(2)
            
        if success:
            cookies = page.cookies(all_domains=True)
            cf = None
            if isinstance(cookies, dict):
                cf = cookies.get('cf_clearance')
            else:
                for c in cookies:
                    if c.get('name') == 'cf_clearance':
                        cf = c.get('value')
                        break
            
            page.quit()
            
            if cf:
                update_config_file(cf)
                return cf
            else:
                return None
        else:
            page.quit()
            return None
            
    except Exception as e:
        logger.error(f"Error saat bypass CF: {e}")
        return None
