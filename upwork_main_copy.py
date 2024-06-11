
from openai import OpenAI
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from screeninfo import get_monitors
import undetected_chromedriver as uc
import openpyxl as pyxl
import time
import random
import math
import re
import requests
import pickle
import os
import threading

#Global Variables
max_wait_time = 10
number_of_suppliers_to_contact = 2
max_retries = 5
chat_product_dict = {} #Key: supplier name, Value: list queue of product tuples (first is current product chat)
chat_step_dict = {} #Key: supplier name, Value: dictionary key: index, value is the chat questions left
chat_product_lock = threading.Lock()
chat_step_lock = threading.Lock()
index_step_dict_lock = threading.Lock()
chat_dict_loc = "chat_product_dict.pkl"
chat_step_dict_loc = "chat_step_dict.pkl"



def with_cooldown(func, max_attempts=5, initial_wait=3):
    attempt = 0
    wait_time = initial_wait

    while attempt < max_attempts:
        try:
            time.sleep(wait_time)
            result = func()
            if isinstance(result, dict) and result.get('error', '') == 'Rate limit exceeded':
                print(f"Rate limit exceeded. Waiting {wait_time} seconds before retrying...")
                wait_time *= 2  # Exponential back-off
                attempt += 1
            else:
                return result
        except Exception as e:
            print(f"An error occurred: {e}")
            if "Rate limit exceeded" in str(e):
                print(f"Rate limit exceeded in exception. Waiting {wait_time} seconds before retrying...")
                wait_time *= 2
                attempt += 1
            else:
                return None  # Return None immediately on other exceptions

    print("Maximum retry attempts reached.")
    return None

def extract_asin(input_string):
    # Regular expression to match an Amazon ASIN within various contexts
    match = re.search(r'(?:dp|ASIN|gp/product)/([A-Z0-9]{10})', input_string)
    if match:
        return match.group(1)  # Return the ASIN
    else:
        return "ASIN not found"
    
def clear_chat_dicts():
    global chat_product_dict
    global chat_product_lock
    global chat_step_dict
    global chat_step_lock

    with chat_product_lock:
        chat_product_dict = {}
    with chat_step_lock:
        chat_step_dict = {}

    write_dict_to_file(chat_dict_loc, chat_product_dict, chat_product_lock)
    write_dict_to_file(chat_step_dict_loc, chat_step_dict, chat_step_lock)

def read_chat_dicts(specific_dict=None):
    global chat_product_dict
    global chat_product_lock
    global chat_step_dict
    global chat_step_lock

    if specific_dict == None:
        with chat_product_lock:
            if os.path.exists(chat_dict_loc):
                with open(chat_dict_loc, 'rb') as chat_file:
                    chat_product_dict = pickle.load(chat_file)
        with chat_step_lock:
            if os.path.exists(chat_step_dict_loc):
                with open(chat_step_dict_loc, 'rb') as chat_file:
                    chat_step_dict = pickle.load(chat_file)
    else:
        if specific_dict == "chat_product_dict":
            with chat_product_lock:
                if os.path.exists(chat_dict_loc):
                    with open(chat_dict_loc, 'rb') as chat_file:
                        chat_product_dict = pickle.load(chat_file)
        elif specific_dict == "chat_step_dict":
            with chat_step_lock:
                if os.path.exists(chat_step_dict_loc):
                    with open(chat_step_dict_loc, 'rb') as chat_file:
                        chat_step_dict = pickle.load(chat_file)


def write_dict_to_file(file_path, global_dict, global_lock):
    
    with global_lock:
        write_retries = 0
        while True:
            with open(file_path, 'wb') as file:
                pickle.dump(global_dict, file)

            # Attempt to read back the dictionary to verify its integrity
            try:
                with open(file_path, 'rb') as file:
                    data_read_back = pickle.load(file)
                # Compare the original dictionary with the read-back data
                if data_read_back == global_dict:
                    break
                else:
                    write_retries += 1
                    if write_retries > max_retries:
                        raise ValueError(f"Pickle file for {file_path} corrupted after writing.") 
            except (pickle.PickleError, EOFError) as e:
                write_retries += 1
                if write_retries > max_retries:
                    raise ValueError(f"Pickle file for {file_path} corrupted after writing.")


def random_sleep(min_time, max_time):
    wait_time = random.uniform(min_time, max_time)
    time.sleep(wait_time)

def query_openai(prompt, model, max_retries=max_retries):
    base_wait = 1  # Base wait time in seconds

    #Obtain OpenAI API Access
    client = OpenAI()

    for i in range(max_retries):
        try:
            if model == "titles":
                #Get simplified titles
                response = client.chat.completions.create(
                model="ft:gpt-3.5-turbo-0125:personal:simplified-titles:96s6KQpr",
                messages=[
                    {"role": "system", "content": "You are a program that needs to return a list of simplified titles from an 'Initial title' and must abide by the given rules. Rule 1: Begin with the 'Initial title' and with each iteration make the simplified title generated less detailed (less characters). Rule 2: In the list of simplified titles returned, have the simplified titles ordered from 1) most detailed (most characters) to 10) least detailed (least characters). Rule 3: Only return simplified titles that are less than 50 characters in total length. Rule 4: Return 10 simplified titles. Rule 5: Do not include character count in the simplified titles. Rule 6: Exclude any brand names from the returned simplified titles unless the product is specific for a brand such as 'brand replacement parts'."},
                    {"role": "user", "content": f"{prompt}"}
                ]
                )
            elif model == "chat_bot":

                current_questions, supplier_response = prompt

                messages=[
                    {"role": "system", "content": f"You are a chatbot that confirms or denies whether these questions have been answered: {current_questions}. Return 'Confirm: ' followed by which question index(s) was answered and what the answer for the specific question was. For example 'Confirm: 1: Yes we sell that'. Return 'PASS' if no question was answered. Return 'PICTURE' if the supplier needs a picture of the product."},
                    {"role": "user", "content": supplier_response}
                ]

                response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages
                )
            return response.choices[0].message.content
        except OpenAI.RateLimitError:
            wait_time = base_wait * math.pow(2, i)  # Exponential backoff formula
            print(f"Rate limit exceeded, waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        except OpenAI.OpenAIError as e:
            print(f"An OpenAI API error occurred: {e}")
            break  # Exit the loop for non-rate-limit errors
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break  # Exit the loop for other errors
    return None  # Return None if all retries fail

def initialize_alibaba_search():
    global max_wait_time

    # Open the Alibaba
    # proxy = '38.154.126.69:8800'
    # chrome_options = Options()
    # chrome_options.add_argument(f'--proxy-server={proxy}')
    # chrome_options.add_argument("--disable-notifications")
    # driver = uc.Chrome(options=chrome_options)
    driver = uc.Chrome()
    monitor = get_monitors()[0]
    screenHeight = monitor.height
    screenWidth = monitor.width
    wait = WebDriverWait(driver, max_wait_time)
    driver.set_window_size(screenWidth * 0.75, screenHeight)
    driver.set_window_position((-1) * screenWidth, 0)
    driver.get('https://www.alibaba.com/')

    # Load and add cookies from the file
    if os.path.exists("alibaba_login_cookies.pkl"):
        with open("alibaba_login_cookies.pkl", "rb") as cookies_file:
            cookies = pickle.load(cookies_file)
            for cookie in cookies:
                driver.add_cookie(cookie)
        
        #Reload View
        random_sleep(0, 1)
        driver.get('https://www.alibaba.com/')
    else:
        #Sign in
        try:
            sign_in_button_class = 'tnh-sign-in'
            sign_in_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, sign_in_button_class)))
            sign_in_button.click()
        except Exception as e:
            x = input(f"{e}")
            raise ValueError("Sign in button not found") 

        #Click login with email
        random_sleep(0, 2)
        try:
            email = 'Your email'
            password = 'Your password'
            login_with_email_css = '.sif_form.sif_form-account'
            password_css = '.sif_form.sif_form-password'
            login_text_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, login_with_email_css)))
            password_text_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, password_css)))
            login_text_box.click()
            login_text_box.send_keys(email)
            login_text_box.send_keys(Keys.TAB)
            password_text_box.send_keys(password)
            password_text_box.send_keys(Keys.RETURN)
        except Exception as e:
            x = input(f"{e}")
            raise ValueError("Login text box not found") 
        
        random_sleep(0, 2)
        cookies = driver.get_cookies()
        with open("alibaba_login_cookies.pkl", "wb") as cookies_file:
            pickle.dump(cookies, cookies_file)
        print("Cookies saved to 'alibaba_login_cookies.pkl'")

    return driver, wait

def final_input_interaction(driver, wait, description_tuple, supplier_name):

    #Get product info
    quantity, rfq_product_name, image_url, max_exw_price = description_tuple

    #Input RFQ Quantity
    random_sleep(0, 1)
    rfq_quantity_input_class = "//span[contains(@class, 'next-input') and contains(@class, 'next-small') and contains(@class, 'next-noborder')]/input"
    try:
        rfq_quantity_input = wait.until(EC.element_to_be_clickable((By.XPATH, rfq_quantity_input_class)))
        rfq_quantity_input.click()
        random_sleep(0, 1)
        rfq_quantity_input.clear()
        random_sleep(0, 1)
        rfq_quantity_input.send_keys(quantity)
    except Exception as e:
        rfq_quantity_input_class = "//div[contains(@class, 'quantity-wrap')]/input"
        try:
            rfq_quantity_input = wait.until(EC.element_to_be_clickable((By.XPATH, rfq_quantity_input_class)))
            rfq_quantity_input.click()
            random_sleep(0, 1)
            rfq_quantity_input.clear()
            random_sleep(0, 1)
            rfq_quantity_input.send_keys(quantity)
        except Exception as e:
            print(f"No rfq quantity when contacting supplier found exception: {e}")
            return True
    
    #Input RFQ Inquiry
    random_sleep(0, 1)
    inquiry_input_id = "inquiry-content"
    inquiry_message = f"Hello, I am interested in purchasing the following product: {rfq_product_name}. Could you please provide me with a quote?"
    try:
        inquiry_input = wait.until(EC.element_to_be_clickable((By.ID, inquiry_input_id)))
        inquiry_input.click()
        random_sleep(0, 1)
        inquiry_input.send_keys(inquiry_message)
    except Exception as e:
        inquiry_input_xpath = "//textarea[contains(@class, 'content-input')]"
        try:
            inquiry_input = wait.until(EC.element_to_be_clickable((By.XPATH, inquiry_input_xpath)))
            inquiry_input.click()
            random_sleep(0, 1)
            inquiry_input.send_keys(inquiry_message)
        except Exception as e:
            print(f"No inquiry input when contacting supplier exception: {e}") 
            return True
    
    #Download Image to sen
    image_download_iter = 0
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_file_path = os.path.join(current_dir, "tmp_image.jpg")
    while True:
        random_sleep(1, 2)
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            with open(tmp_file_path, 'wb') as tmp_file:
                tmp_file.write(image_response.content)
            break
        else:
            if image_download_iter > max_retries:
                print(f"Didn't download image for contacting supplier exception: {e}") 
                return True
            image_download_iter += 1

    #Input RFQ Image
    random_sleep(0, 1)
    image_input_id = "ksu-fileserver-1"
    try:
        image_input = wait.until(EC.presence_of_element_located((By.ID, image_input_id)))
        image_input.send_keys(tmp_file_path)
    except Exception as e:
        image_input_xpath = "/html/body/div[1]/div/div/div/div[2]/div[2]/div/div[1]/input"
        try:
            image_input = wait.until(EC.presence_of_element_located((By.XPATH, image_input_xpath)))
            image_input.send_keys(tmp_file_path)
        except Exception as e:
            print(f"Couldn't send image when contacting supplier exception: {e}") 
            return True
        
    #Send Inquiry
    random_sleep(0, 1)
    send_inquiry_button_xpath = "/html/body/div[1]/div/div/div/div[3]/button"
    try:
        send_inquiry_button = wait.until(EC.element_to_be_clickable((By.XPATH, send_inquiry_button_xpath)))
        send_inquiry_button.click()
    except Exception as e:
        send_inquiry_button_xpath = "/html/body/div[2]/div/form/div[1]/div[2]/div/div/div[2]/input"
        try:
            send_inquiry_button = wait.until(EC.element_to_be_clickable((By.XPATH, send_inquiry_button_xpath)))
            send_inquiry_button.click()
            send_inquiry_button.click()
        except Exception as e:
            print(f"Couldn't send inquiry for supplier exception: {e}") 
            return True

    #See if successful and delete temp file
    random_sleep(1, 2)
    succeded_page_id = "alitalk-dialog-inquiry-succeed"
    try:
        driver.switch_to.default_content()
        wait.until(EC.presence_of_element_located((By.ID, succeded_page_id)))
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
    except Exception as e:
        succeded_page_icon = "//i[contains(@class, 'ui2-icon-success')]"
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, succeded_page_icon)))
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
        except Exception as e:
            print(f"Didn't have successful inquiry for supplier exception: {e}") 
            return True

    #Add chat product history (initial chat not included in chat since should be included in steps)
    with chat_product_lock:
        print(f"Adding to product dict supplier : {supplier_name}")
        chat_product_dict[supplier_name] = []
        chat_product_dict[supplier_name].append(description_tuple)

    async_thread = threading.Thread(target=write_dict_to_file, args=(chat_dict_loc, chat_product_dict, chat_product_lock))
    async_thread.start()

    #Close inquiry tab
    random_sleep(0, 1)
    change_win_iter = 0
    while True:
        random_sleep(1, 2)
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            break
        except Exception as e:
            if change_win_iter > max_retries:
                print(f"Couldn't change windows for contacting supplier exception: {e}") 
                return True
            change_win_iter += 1
    
    return False

def send_initial_message(driver, wait, search_term, rfq_info, first_search, supplier_set):

    #Initialize variables
    global number_of_suppliers_to_contact
    global max_retries
    global chat_product_dict
    global chat_product_lock

    if first_search:
        #Search box
        try:
            search_bar_class = 'search-bar-placeholder'
            search_bar = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, search_bar_class)))
            search_bar.click()
        except Exception as e:
            pass
        
        random_sleep(0, 1)
        
    try:
        search_input_class = 'search-bar-input'
        search_input_box = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, search_input_class)))
        search_input_box.clear()
        random_sleep(0, 1)
        search_input_box.send_keys(search_term)
        random_sleep(1, 2)
        search_input_box.send_keys(Keys.RETURN)
    except Exception as e:
        
        raise ValueError("Search input box not found exception: {e}") 
    
    random_sleep(2, 3)
    supplier_name_class = "search-card-e-company"
    try:
        text_elements = wait.until(EC.visibility_of_all_elements_located((By.CLASS_NAME, supplier_name_class)))
    except Exception as e:
        
        raise ValueError(f"No name of supplier found search term: {search_term} exception: {e}") 
    
    random_sleep(0, 1)
    supplier_image_class = "search-card-e-slider__wrapper"
    try:
        image_elements = wait.until(EC.visibility_of_all_elements_located((By.CLASS_NAME, supplier_image_class)))
    except Exception as e:
        
        raise ValueError(f"No image of supplier found search term: {search_term} exception: {e}") 

    #Contact suppliers button on first page
    random_sleep(0, 1)
    contact_suppliers_buttons = []
    try:
        contact_suppliers_button_class = "//a[contains(@class, 'search-card-e-abutton') and contains(@class, 'search-card-e-action-abutton') and contains(@class, 'search-card-e-contact-supplier') and contains(@class, 'search-card-e-abutton-large')]"
        contact_suppliers_buttons = wait.until(EC.visibility_of_all_elements_located((By.XPATH, contact_suppliers_button_class)))
    except Exception as e:
        print(f"No contact suppliers button found search term: {search_term} exception: {e}")


    #Contact suppliers
    current_supplier_index = 0
    for _ in range(number_of_suppliers_to_contact):

        #iterate over contact suppliers
        for contact_button in contact_suppliers_buttons:
            random_sleep(0, 3)
            try:
                contact_button.click()
            except ElementClickInterceptedException:
                actions = ActionChains(driver)
                actions.move_to_element(contact_button).perform()
                random_sleep(0, 1)
                contact_button.click()
            except Exception as e:
                raise ValueError(f"Couldn't click contact supplier button search term: {search_term} exception: {e}")
            
            #Switch window view
            random_sleep(2, 3)
            change_win_iter = 0
            while True:
                random_sleep(1, 2)
                try:
                    if len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[1])
                    break
                except Exception as e:
                    if change_win_iter > max_retries:
                        
                        raise ValueError(f"Couldn't change windows for contacting supplier search term: {search_term} index: {j} exception: {e}") 
                    change_win_iter += 1
            
            #Get supplier name
            supplier_name_class = "company-name"
            try:
                text_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, supplier_name_class)))
            except Exception as e:
                
                raise ValueError(f"No name of supplier found exception: {e}") 
            
            supplier_name = text_element.text
            if supplier_name not in supplier_set:
                supplier_set.add(supplier_name)

                #See if supplier is already in chat
                quantity = rfq_info[0]
                rfq_product_name = rfq_info[1]
                image_url = rfq_info[2]
                max_exw_price = rfq_info[3]
                description_tuple = (quantity, rfq_product_name, image_url, max_exw_price)
                with chat_product_lock:
                    if supplier_name in chat_product_dict:
                        current_chat_list = len(chat_product_dict[supplier_name])
                        if current_chat_list != 0:
                            #Don't contact yet if supplier is already in chat
                            chat_product_dict[supplier_name].append(description_tuple)
                            break
                
                errors = final_input_interaction(driver, wait, description_tuple, supplier_name)
                if errors:
                    check_error = input("Error in sending message. Continue? (y/n)")
                    if check_error.lower() == 'n':
                        driver.quit()
                
                break
            else:
                #Close inquiry tab
                random_sleep(0, 1)
                change_win_iter = 0
                while True:
                    random_sleep(0, 1)
                    try:
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        break
                    except Exception as e:
                        if change_win_iter > max_retries:
                            print(f"Couldn't change windows for contacting supplier exception: {e}") 
                            return True
                        change_win_iter += 1

            



        for j in range(current_supplier_index, len(text_elements)):
            #Close inquiry tab if any
            change_win_iter = 0
            while True:
                random_sleep(0, 1)
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    break
                except Exception as e:
                    if change_win_iter > max_retries:
                        print(f"Couldn't change windows for contacting supplier exception: {e}") 
                        return True
                    change_win_iter += 1

            try:
                supplier_name = text_elements[j].text
            except Exception as e:
                print(f"Couldn't get supplier name search term: {search_term} index: {j} exception: {e}")
                x = input("Continue?")
            if supplier_name not in supplier_set:
                #Store supplier to avoid duplicates
                current_supplier_index = j
                supplier_set.add(supplier_name)

                #See if supplier is already in chat
                quantity = rfq_info[0]
                rfq_product_name = rfq_info[1]
                image_url = rfq_info[2]
                max_exw_price = rfq_info[3]
                description_tuple = (quantity, rfq_product_name, image_url, max_exw_price)
                with chat_product_lock:
                    if supplier_name in chat_product_dict:
                        current_chat_list = len(chat_product_dict[supplier_name])
                        if current_chat_list != 0:
                            #Don't contact yet if supplier is already in chat
                            chat_product_dict[supplier_name].append(description_tuple)
                            break
                    #Else statements for adding to product dict is later to ensure message is sent

                #Contact supplier
                random_sleep(1, 2)
                try:
                    image_elements[j].click()
                except Exception as e:
                    
                    raise ValueError(f"Couldn't click image of supplier search term: {search_term} index: {j} exception: {e}") 

                #Switch window view
                random_sleep(2, 3)
                change_win_iter = 0
                while True:
                    random_sleep(1, 2)
                    try:
                        if len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[1])
                        break
                    except Exception as e:
                        if change_win_iter > max_retries:
                            
                            raise ValueError(f"Couldn't change windows for contacting supplier search term: {search_term} index: {j} exception: {e}") 
                        change_win_iter += 1

                #Click Contact Supplier button
                last_height = 0
                while True:
                    #Scroll down page
                    pixel_increment = 100
                    new_height = last_height + pixel_increment
                    driver.execute_script(f"window.scrollTo(0, {new_height});")
                    random_sleep(0, 1)
                    contact_supplier_button_selector = "button[data-type-btn='inquiry']"
                    try:
                        contact_button = driver.find_element(By.CSS_SELECTOR, contact_supplier_button_selector)
                        contact_button.click()
                        break
                    except Exception as e:
                        if new_height >= max_retries * pixel_increment:
                            
                            raise ValueError(f"No contact_button for supplier found search term: {search_term} index: {j} exception: {e}") 
                        last_height = new_height
                
                #Change to iframe
                popup_iter = 0
                while True:
                    random_sleep(1, 2)
                    popup_class_id = "alitalk-dialog-iframe"
                    try:
                        popup_iframe_element = driver.find_element(By.CLASS_NAME, popup_class_id)
                        driver.switch_to.frame(popup_iframe_element)
                        break
                    except Exception as e:
                        if popup_iter > max_retries:
                            
                            raise ValueError(f"Didn't change to supplier popup search term: {search_term} index: {j} exception: {e}") 
                        popup_iter += 1
                
                errors = final_input_interaction(driver, wait, description_tuple, supplier_name)
                if errors:
                    check_error = input("Error in sending message. Continue? (y/n)")
                    if check_error.lower() == 'n':
                        driver.quit()

                break

    return supplier_set

def create_chat_steps(supplier_name):
    global chat_step_dict
    global chat_step_lock
    global chat_product_dict
    global chat_product_lock

    with chat_product_lock:

        if supplier_name in chat_product_dict:
            product_tuple = chat_product_dict[supplier_name]
            product_name = ""
            quantity = 0
            if isinstance(product_tuple, list):
                quantity = product_tuple[0][0]
                product_name = product_tuple[0][1]
            else:
                quantity = product_tuple[0]
                product_name = product_tuple[1]
     

            #See if chat steps already exist
            if supplier_name in chat_step_dict:
                current_step_dict = chat_step_dict[supplier_name]
                return current_step_dict
            else:                
                #Add preset steps
                confirm = f"Are you selling {product_name}?"
                exw_price_step = f"What is the EXW price for {quantity} units?"
                # exw_price_threshold_step = f"Confirm price given is less than {exw_max_price_str}"
                sample = "Can I get a sample?"
                package_dim_step = "What are the package dimensions?"
                package_weight_step = f"What is the package weight for {quantity} units?"
                product_brand_step = "Does the product come unbranded?"
                picture = "Would I be able to get a picture?"
                spec_steps = {1: confirm, 2: exw_price_step, 3: sample, 4: package_dim_step, 5: package_weight_step, 6: product_brand_step, 7: picture}
                chat_step_dict[supplier_name] = spec_steps
                async_thread = threading.Thread(target=write_dict_to_file, args=(chat_step_dict_loc, chat_step_dict, chat_step_lock))
                async_thread.start()

                return spec_steps
            
        else:
            raise ValueError(f"Supplier: {supplier_name} not in chat_product_dict")
        

def resend_image(driver, supplier_name):
    global chat_product_dict
    global chat_product_lock

    #Get image url
    with chat_product_lock:
        if supplier_name in chat_product_dict:
            image_url = ""
            if isinstance(chat_product_dict[supplier_name], list):
                image_url = chat_product_dict[supplier_name][0][2] 
            else:
                image_url = chat_product_dict[supplier_name][2]
            image_download_iter = 0
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tmp_file_path = os.path.join(current_dir, "tmp_image.jpg")
            while True:
                random_sleep(1, 2)
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    with open(tmp_file_path, 'wb') as tmp_file:
                        tmp_file.write(image_response.content)
                    break
                else:
                    if image_download_iter > max_retries:
                        
                        raise ValueError(f"Didn't download image for resending image") 
                    image_download_iter += 1
            #Send Image
            random_sleep(2, 4)
            try:
                js_script = "arguments[0].style.display = 'block';"
                file_input = driver.find_element(By.NAME, "file")
                driver.execute_script(js_script, file_input)
                file_input.send_keys(tmp_file_path)
            except Exception as e:
                
                raise ValueError(f"Couldn't resend image exp: {e}") 
            

        else:
            raise ValueError(f"Supplier: {supplier_name} not in chat_product_dict")
    
def delete_chat_convo(driver, supplier_name = None):
    global chat_product_dict
    global chat_product_lock


    #Delete chat history
    if supplier_name != None:
        with chat_product_lock:
            if supplier_name in chat_product_dict:
                if isinstance(chat_product_dict[supplier_name], list):
                    chat_product_dict[supplier_name] = chat_product_dict[supplier_name].pop(0)
                else:
                    del chat_product_dict[supplier_name]
        async_thread = threading.Thread(target=write_dict_to_file, args=(chat_dict_loc, chat_product_dict, chat_product_lock))
        async_thread.start()

        with chat_step_lock:
            if supplier_name in chat_step_dict:
                del chat_step_dict[supplier_name]
        async_thread = threading.Thread(target=write_dict_to_file, args=(chat_step_dict_loc, chat_step_dict, chat_step_lock))
        async_thread.start()


    #Obtain selected element
    try:
        element_selected_css_selector = ".contact-item-container.selected"
        element_selected = driver.find_element(By.CSS_SELECTOR, element_selected_css_selector)
        element_selected.click()
    except:
        print(f"Couldn't find selected element for supplier: {supplier_name} to delete chat")
        return
    
    random_sleep(1, 2)
    try:
        open_chat_delete_option_class = ".im-next-icon.im-next-icon-ellipsis.im-next-xs"
        open_chat_delete_option = element_selected.find_element(By.CSS_SELECTOR, open_chat_delete_option_class)
        open_chat_delete_option.click()
        random_sleep(0, 1)
    except:
        raise ValueError(f"Couldn't click on open delete chat for supplier: {supplier_name}")
    
    try:
        delete_chat_xpath = "//span[@class='menu-content' and contains(text(), 'Delete')]"
        delete_chat = driver.find_element(By.XPATH, delete_chat_xpath)
        delete_chat.click()
        random_sleep(0, 1)
    except:
        raise ValueError(f"Couldn't click delete chat for supplier: {supplier_name}")
    

def monitor_chats(driver):
    global chat_step_dict
    global chat_step_lock
    global chat_product_dict
    global chat_product_lock
    
    #Get to chat page
    chat_page_url = "https://message.alibaba.com/message/messenger.htm#/"
    driver.get(chat_page_url)
    random_sleep(3, 4)

    clicked_on_unread_tab = False
    blocked_counter = 0
    last_response = ""
    while True:
        print("Checking for new messages")

        #Check if suggestions popup
        try:
            suggestions_popup_class = "label-tip-container"
            suggestions_popup = driver.find_element(By.CLASS_NAME, suggestions_popup_class)
            random_sleep(0, 1)
   
            #Close suggestions popup
            close_suggestions_popup_xpath = ".//button[contains(@class, 'im-next-btn') and contains(@class, 'im-next-medium') and contains(@class, 'im-next-btn-primary')]"
            close_button = suggestions_popup.find_element(By.XPATH, close_suggestions_popup_xpath)
            close_button.click()
            random_sleep(0, 1)
        except:
            pass



        if clicked_on_unread_tab == False:
            try:
                unread_tab_class = "red-num"
                unread_tab = driver.find_element(By.CLASS_NAME, unread_tab_class)
                number_unread = int(unread_tab.text)

                if number_unread != 0:
                    unread_tab.click()
                    clicked_on_unread_tab = True
                    random_sleep(1, 2)
                else:
                    random_sleep(5, 10)
                    continue
            except:
                random_sleep(5, 10)
                pass
        else:
            #Sleep to give time for unread tab to load
            random_sleep(5, 10)

        #Get unread elements if any in current_tab
        try:
            unread_item_container_class = "unread-list-container"
            unread_element_container = driver.find_element(By.CLASS_NAME, unread_item_container_class)
            blocked_counter = 0
        except:
            print("No unread element container")
            blocked_counter += 1
            if blocked_counter > max_retries:
                chat_page_url = "https://message.alibaba.com/message/messenger.htm#/"
                driver.get(chat_page_url)
                random_sleep(3, 4)
            continue
        random_sleep(1, 2)
        try:
            unread_item_class = "contact-item-container"
            element = unread_element_container.find_element(By.CLASS_NAME, unread_item_class)
            blocked_counter = 0
        except:
            print("No unread elements")
            blocked_counter += 1
            if blocked_counter > max_retries:
                chat_page_url = "https://message.alibaba.com/message/messenger.htm#/"
                driver.get(chat_page_url)
                random_sleep(3, 4)
            continue
        
        random_sleep(2, 3)
        #Iterate through unread elements
        try:
            supplier_name = element.find_element(By.CLASS_NAME, "contact-company").text
        
        except: 
            x = input("Couldn't get supplier name for unread element")
            raise ValueError(f"Couldn't get supplier name for unread element")

        try:
            unread_data_count = element.get_attribute('data-unread-count')
        except:
            raise ValueError(f"Couldn't get unread data count for supplier: {supplier_name}")

        
        #Click on chat
        try:
            random_sleep(0, 1)
            element.click()
            random_sleep(1, 2)
        except:
            raise ValueError(f"Couldn't click on unread element for supplier: {supplier_name}")

        try:
            new_message_element_parents = driver.find_elements(By.XPATH, "//div[contains(@class, 'item-content') and contains(@class, 'item-content-left')]")
        except:
            raise ValueError(f"Couldn't get new message element parents for supplier: {supplier_name}")
        
        random_sleep(1, 2)
        unread_data_count = int(unread_data_count)
        start_index_parent = 0
       
        if len(new_message_element_parents) < unread_data_count:
            start_index_parent = 0
        else:
            start_index_parent = len(new_message_element_parents) - unread_data_count

        new_message_array = []
        for i in range(start_index_parent, len(new_message_element_parents)):
            new_message_element_parent = new_message_element_parents[i]
            try:
                new_message_element = new_message_element_parent.find_element(By.XPATH, ".//div[contains(@class, 'session-rich-content') and contains(@class, 'text')]")
            except:
                continue
            new_message_text = new_message_element.text
            new_message_array.append(new_message_text)
        if len(new_message_array) == 0:
            #First message is just an image or sent you to different person (wait for another message)
            continue
            

        new_messages = '||'.join(new_message_array[::-1])
        if last_response == new_messages:
            #Repeat due to alibaba loading slow
            continue
        else:
            last_response = new_messages

        chat_step_array = []
        current_product = ""
        chat_bot_model = "chat_bot"
        max_price = 0.0
        delete_chat = False
        try:
            chat_step_dict = create_chat_steps(supplier_name)
            for index, (key, value) in enumerate(chat_step_dict.items(), start=1):
                question = f"{index}. {value}"
                chat_step_array.append(question)

            with chat_product_lock:
                current_product = ""
                if isinstance(chat_product_dict[supplier_name], list):
                    current_product = chat_product_dict[supplier_name][0][1]
                    try:
                        max_price = float(chat_product_dict[supplier_name][0][3])
                    except:
                        raise ValueError(f"Couldn't get max price for supplier: {supplier_name} price: {chat_product_dict[supplier_name][0][3]}")
                else:
                    current_product = chat_product_dict[supplier_name][1]
                    try:
                        max_price = float(chat_product_dict[supplier_name][3])
                    except:
                        raise ValueError(f"Couldn't get max price for supplier: {supplier_name} price: {chat_product_dict[supplier_name][3]}")
        except Exception as e:
            delete_chat_convo(driver)
            close_chat(driver)
            continue
        
        #Determine what questions were answered by supplier
        current_chat_step_string = " ".join(chat_step_array)
        chat_tuple = (current_chat_step_string, new_messages)
        chat_response = query_openai(chat_tuple, chat_bot_model)
        print(f"Initial chat response: {chat_response}")
        if chat_response:
            #Use regex to get indexes of answered questions use another GPT to check whether the questions were good (END if not, remove from array if good)
            if chat_response.__contains__("Confirm: "):
                numbers_string = chat_response.replace("Confirm: ", "")
                # Regular expression to match the pattern "index: answer"
                pattern = r'(\d+):\s*([^:]+?)(?=\s*\d+:|$)'
                matches = re.findall(pattern, numbers_string, re.IGNORECASE)
                answers_dict = {int(index): answer.strip() for index, answer in matches}

                #Remove from chat steps if good
                indexes_left = sorted(list(chat_step_dict.keys()))
                for index in answers_dict:
                    corrected_index = index - 1
                    initial_index = indexes_left[corrected_index]
                    del chat_step_dict[supplier_name][initial_index]
                
                #Save changes
                async_thread = threading.Thread(target=write_dict_to_file, args=(chat_step_dict_loc, chat_step_dict, chat_step_lock))
                async_thread.start()
                    

            if len(chat_step_dict[supplier_name]) == 0:
                #All questions answered
                delete_chat = True
                chat_response = "Thanks for all the info you provided. I need to talk to my supervisor and I'll get back to you once we reach a decision. Have a great day!"
                #TODO Save info to spreadsheet
            elif chat_response.__contains__("PICTURE"):
                resend_image(driver, supplier_name)
            else:
                #Send questions remaining
                second_chat_question_array = []
                for index, (key, value) in enumerate(chat_step_dict.items(), start=1):
                    question = f"{index}. {value}"
                    second_chat_question_array.append(question)
                chat_response = "\n".join(second_chat_question_array)
                chat_response = "Hello, can you please answer the following questions:\n" + chat_response + "\n (preferably in 1. 2. 3, etc. format to avoid confusion)"

            print(f"Chat response: {chat_response}")
            cont = input("Continue?")
            #Send chat response
            try:
                message_element_class = "send-textarea"
                message_element = driver.find_element(By.CLASS_NAME, message_element_class)
                message_element.click()
                random_sleep(0, 1)
                message_element.send_keys(chat_response)
                random_sleep(0, 1)

                send_button_xpath = "//button[contains(@class, 'im-next-btn') and contains(@class, 'send-tool-button')]"
                send_button = driver.find_element(By.XPATH, send_button_xpath)
                send_button.click()
            except:
                raise ValueError(f"Couldn't send chat response for supplier: {supplier_name}")
        else:
            raise ValueError(f"Failed to get chat response for supplier: {supplier_name}")
        

        if delete_chat == True:
            delete_chat_convo(driver, supplier_name)
        
        close_chat(driver)

def close_chat(driver):
    #Close chat
    try:
        unread_tab_xpath = "//span[@class='im-next-tabs-tab-inner-title' and @title='Unread']"
        unread_tab = driver.find_element(By.XPATH, unread_tab_xpath)
        unread_tab.click()
    except:
        raise ValueError(f"Couldn't click on unread tab to close")

def read_data():
    # Initialize session and capture data
    export_name = 'upwork_sample.xlsx'
    workbook = pyxl.load_workbook(export_name)
     
    sheet = workbook['Sheet1']

    # Initialize an empty list to store rows
    all_needed_values = []

    # Iterate over the rows in the sheet
    important_columns = {'search term','amzn link', 'order details', 'rfq quantity', 'rfq product name', 'rfq item description', 'max exw price', 'max size'}
    important_columns_indexes = set()
    for i, row in enumerate(sheet.iter_rows(values_only=False), start=1):
        row_values = []
        error_columns = important_columns_indexes.copy()

        for j, cell in enumerate(row, start=1):
            #Get cell color
            if cell.fill.fill_type is None or cell.fill.fgColor.rgb == "FFFFFFFF":
                #Only get white cells
                value = cell.value
                if i == 1:
                    if value is not None:
                        formatted_column_name = value.strip().lower()
                        if formatted_column_name in important_columns:
                            important_columns_indexes.add(j)
                elif j in important_columns_indexes:
                    error_columns.remove(j)
                    if cell.hyperlink:
                        row_values.append(cell.hyperlink.target)
                    else:
                        row_values.append(value)

        # Add the row's values to the all_values list
        if len(row_values) != len(important_columns):
            if len(row_values) > 0:
                print(f"Error in row: {row_values}  column(s): {error_columns}")
        else:
            all_needed_values.append(row_values)

    
    
    return all_needed_values


def main():

    #Load Data
    data = read_data()

    #Load Current Chat State
    read_chat_dicts()

    #Init Alibaba
    driver, wait = initialize_alibaba_search()

    amazon_info_list = []
    with open('amazon_info_list.pickle', 'rb') as f:
        amazon_info_list = pickle.load(f)
        print("Loaded amazon info list")
    current_len_amazon_info = len(amazon_info_list)

    #Send initial messages
    prompt = input("All or just monitor (all/m)? ")
    if prompt.lower() == 'all':
        first_search = False
        for i, item_row in enumerate(data[:current_len_amazon_info]):
            #Get ASIN info
            try:
                search_term_index = 0
                amazon_link_index = 1
                rfq_quantity_index = 3
                rfq_product_name_index = 4
                rfq_description_index = 5
                max_exw_price_index = 6
                search_term = item_row[search_term_index]
                link_asin = ((item_row[amazon_link_index].split('"'))[1]).split('/')[-1]
                rfq_quantity = item_row[rfq_quantity_index]
                rfq_product_name = item_row[rfq_product_name_index]
                max_exw_price = item_row[max_exw_price_index]
            except:
                print(f"Error in getting data for row: {item_row}")
                continue


            main_image_url, title = amazon_info_list[i]
        
 
            print("About to be Searched Title: ", title)
            #Get simplified titles
            simplified_titles = None
            title_prompt = f'Initial title: {title}'
            title_model = "titles"
            response = query_openai(title_prompt, title_model)
            if response:
                simplified_titles = response.split("\n")
                simplified_titles = [re.sub(r'^\s*[\d]+[).]\s*|^\s*-\s*', '', title).strip() for title in simplified_titles if title.strip()]
                print(f"{simplified_titles}")
            else:
                raise ValueError(f"Failed to get simplified titles for title: {title}")
    
            #Open Alibaba and send initial messages
            supplier_set = set()
            rfq_info = [rfq_quantity, rfq_product_name, main_image_url, max_exw_price]
            for j, simplified_search_term in enumerate(simplified_titles):
                print(f"Searching for: {simplified_search_term}")
                if i == 0 and j == 0:
                    first_search = True
                else:
                    first_search = False

                supplier_set = send_initial_message(driver, wait, simplified_search_term, rfq_info, first_search, supplier_set)


        #Monitor chats
        # monitor_chats(driver)
    else:
        monitor_chats(driver)


if __name__ == '__main__':
    main()


    

