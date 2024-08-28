#  pip install openai selenium screeninfo undetected-chromedriver openpyxl python-dotenv gspread gspread-formatting oauth2client requests Flask

# Now you can access the API key using os.getenv
api_key = ""
  
    
import requests
import schedule

def api_call(request_url, request_method, payload_body=None):
    try:
        print("-------------call API---------------")
        if request_method.upper() == "POST":
            response = requests.post(request_url, json=payload_body)
        elif request_method.upper() == "GET":
            response = requests.get(request_url, params=payload_body)
        else:
            return "Unsupported request method"
        
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        return response
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"


from openai import OpenAI
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
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
import inspect
from dotenv import load_dotenv

import gspread
from gspread_formatting import *
from oauth2client.service_account import ServiceAccountCredentials
import json
from enum import Enum


# Global variables
max_wait_time = 60
number_of_suppliers_to_contact = 1
max_retries = 2
chat_product_dict = {} #Key: supplier name, Value: list queue of product tuples (first is current product chat)
chat_step_dict = {} #Key: supplier name, Value: dictionary key: index, value is the chat question left
chat_product_lock = threading.Lock()
chat_step_lock = threading.Lock()
index_step_dict_lock = threading.Lock()
excel_lock = threading.Lock()
chat_dict_loc = "chat_product_dict.pkl"
chat_step_dict_loc = "chat_step_dict.pkl"
current_products_loc = "current_products.pkl"

def getProductName(data,supplier_to_find):
    # Find the root key containing the supplier
    productName = None
    for key, value in data.items():
        if 'suppliers' in value and supplier_to_find in value['suppliers']:
            productName = key
            break
    return productName 

def savePklFIle(file_path,fileData):
    with open(file_path, 'wb') as file:
        pickle.dump(fileData, file)

def askAi(chatThread,questions):
    
    #Obtain OpenAI API Access
    client = OpenAI(api_key=api_key)
    quetions_in_str = '\n '.join(questions.keys())
    messages=[
        {"role": "system", "content": "Act as a bulk buyer from the alibaba.com.\nWe are operating from the USA.\n\n\n###########################\n{ type: \"json_object\" }\nReply in JSON FORMAT only:\n\nEXAMPLE FORMAT:\n{\n   \"flag_kill_thread\":false,\n   \"reply_message\":\"string\",\"extracted_answers\":\n   {\n    \"Are you selling Infrared Thermometer?\": \"unsure\",\n    \"What is the EXW price for 1000 units?\": \"unsure\",\n    \"Can I get a sample?\": \"unsure\",\n    \"What are the package dimensions?\": \"unsure\",\n    \"What is the package weight for 1000 units?\": \"unsure\",\n    \"Does the product come unbranded?\": \"unsure\",\n    \"Would I be able to get a picture?\": \"unsure\"\n  }\n}\n\n\n\n###########################\nSET \"flag_kill_thread\" =true if seller can't supply this to us.\n\n\n ALWAYS GIVE \"extracted_answers\" OBJECT IN YOUR REPLY  \n\n\nYOUR TASK IS TO GET ANSWERS OF ALL THE FOLLOWING QUESTIONS:\n\n"+quetions_in_str+"\n\nCURRENT CHAT THREAD:\n\n"+json.dumps(chatThread, indent=4)+"\n\n\n"},
        {
            "role": "assistant",
            "content": "Analyze the chat thread"
        },
        {
            "role": "user",
            "content": "Give me the follow up question. "
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"}
    )
    print(f"+++++++++++AI response = {response}")
    print(response.choices[0].message.content)
    print("++++++++++++7.1+++++response.choices[0].message.content++++++++++++++++++++++++++++++++++++++++++++++")
    return json.loads(response.choices[0].message.content)



def random_sleep(min_time, max_time):
    wait_time = random.uniform(min_time, max_time)
    time.sleep(wait_time)

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
    # driver.set_window_position((-1) * screenWidth, 0)
    driver.get('https://www.alibaba.com/')

    # Load and add cookies from the file
    if os.path.exists("alibaba_login_cookies.pkl"):
        with open("alibaba_login_cookies.pkl", "rb") as cookies_file:
            print("Loading cookies...")
            cookies = pickle.load(cookies_file)
            for cookie in cookies:
                driver.add_cookie(cookie)
        
        #Reload View
        random_sleep(0, 1)
        driver.get('https://www.alibaba.com/')
        print("Reload view with cookies")
        random_sleep(1,3)
    else:
        #Sign in
        try:
            driver.get('https://login.alibaba.com/newlogin/icbuLogin.htm?return_url=https%3A%2F%2Fwww.alibaba.com%2F&_lang=')
        except Exception as e:
            raise ValueError(f"Sign in button not found, exception: {e}")

        #Click login with email
        random_sleep(0, 2)
        try:
            email = 'nikunj@acedataanalytics.com'
            password = 'Nikunj@123'
            login_with_email_css = '.sif_form.sif_form-account'
            password_css = '.sif_form.sif_form-password'
            submit_btn_xpath = "//button[contains(@class, 'sif_form-submit')]"

            login_text_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, login_with_email_css)))
            password_text_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, password_css)))
            submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, submit_btn_xpath)))

            login_text_box.click()
            login_text_box.send_keys(email)
            password_text_box.send_keys(password)
            submit_btn.click()

        except Exception as e:
            raise ValueError(f"Login text box not found, exception: {e}")
        
        random_sleep(0, 2)
        cookies = driver.get_cookies()
        with open("alibaba_login_cookies.pkl", "wb") as cookies_file:
            pickle.dump(cookies, cookies_file)
        print("Cookies saved to 'alibaba_login_cookies.pkl'")

    return driver, wait

def read_pickle_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            data = pickle.load(file)
            print(data)
            return data
    except Exception as e:
        print(f"An error occurred while reading the pickle file: {e}")

def load_all_seller():    
    with open(chat_step_dict_loc, 'rb') as chat_file:
      sellerData = pickle.load(chat_file)
    # sellerData = read_pickle_file("chat_step_dict.pkl")
    print(type(sellerData))
    # sellerData = json.loads(sellerData)
    return sellerData
    

def load_monitor():
    sellerData = load_all_seller()
    print("++++++++++++++++++++sellerData+++++++++++")
    print(sellerData)
    

    driver, wait = initialize_alibaba_search()
        #Get to chat page
    chat_page_url = "https://message.alibaba.com/message/messenger.htm#/"
    driver.get(chat_page_url)
    # random_sleep(5, 6)

    print("Removing Tip_window")
    random_sleep(3, 4)

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

    #  click ob the first seller
    try:
        item_container_class = "contact-item-container"
        first_text_element = driver.find_element(By.CLASS_NAME, item_container_class)
        all_text_elements = driver.find_elements(By.CLASS_NAME, item_container_class)
    except:
        print("Failed to select first element container")
        blocked_counter += 1
        if blocked_counter > max_retries:
            chat_page_url = "https://message.alibaba.com/message/messenger.htm#/"
            driver.get(chat_page_url)
            random_sleep(3, 4)
        # continue

    print("clicking...")

    for element in all_text_elements:
        current_supplier_name = element.find_element(By.CLASS_NAME, "contact-company")
        current_supplier_name_txt=current_supplier_name.get_attribute('innerText')
        current_supplier_contact_person = element.find_element(By.CLASS_NAME, "contact-info").find_element(By.CLASS_NAME, "name ")
        print(f"++++++++++++++++++++++current_supplier_name+++++++++++++++++{current_supplier_name.get_attribute('innerText')}++++++++")
        print(f"++++++++++++++++++++++current_supplier_contact_person+++++++++++++++++++++++++",current_supplier_contact_person.get_attribute('innerText'))
        try:
            all_question=sellerData[current_supplier_name_txt]
            print(f"++++++++++++++++++++++all_question++++++++++++++++")
            print(all_question)
        except:
            continue


        # check id supplier is present in current_products
         
        current_products = read_pickle_file(current_products_loc)
        print('----------------------********************************* -------------------------')
        print(current_products)
        print('----------------------print(current_products) -------------------------')

        # current_products[current_supplier_name]["suppliers"]
        # savePklFIle(current_products_loc,current_products)

        flagSupplierFound = False
        supplierKey = -1
        # First loop to iterate over the items in the outer dictionary
        for key, value in current_products.items():
            if value['flag_search_completed'] == False:
                # Second loop to iterate over the list of suppliers
                for supplier in value['suppliers']:
                    if supplier == current_supplier_name_txt:
                        # If we find the supplier, print it
                        supplierKey=key
                        print(supplier)
                        print(key)
                        print("+++++++++++++++++++++++++++6.8++++++++++++++++")
                        flagSupplierFound= True
        
        if flagSupplierFound == False : 
            continue

        # Get all keys and join them into a string
        # quetions_in_str = ', '.join(all_question.keys())
        # print(quetions_in_str)


        # click on first seller 
        element.click()
        random_sleep(3, 4)

       
        # # Scroll up 10 times
        # message_item = driver.find_element(By.CLASS_NAME, 'message-item-wrapper')
        # message_item.click()
        # time.sleep(2)  # Wait for the scroll bar to appear

        # scroll_height = 500  # Adjust the scroll height as needed
        # for _ in range(20):
        #     message_item.send_keys(Keys.PAGE_UP)
        #     time.sleep(1)  # wait for a short time to see the effect
        #     print("======================scroll===============================")
        # random_sleep(40,60)
        
        
        messanger_container =  driver.find_element(By.CLASS_NAME, "messenger-content-container")
        all_mess_el = messanger_container.find_elements(By.CLASS_NAME, "message-item-wrapper")

        del all_mess_el[:2]
        # each message
        messageThread = []
        flag_last_message_by_seller = False
        for message_el in all_mess_el:
            messageType = "me"
            flag_last_message_by_seller = False
            if 'item-left-text' in message_el.get_attribute('class').split():
                messageType = "supplier"
                flag_last_message_by_seller = True

            message = {'type': messageType, 'message': message_el.get_attribute('data-original')}    
            messageThread.append(message)    
            print(message)
        
        # If last message sent by us than wait for sellers reply
        if flag_last_message_by_seller != True:
            continue 

        aiResponse =askAi(messageThread,all_question)   
        if 'reply_message' in aiResponse and 'flag_kill_thread' in aiResponse  and 'extracted_answers' in aiResponse:
            print("++++++++++++++++all keys are present log+++++++++++++log_ai_1.1+++++++++++++")
        else:
            print("++++++++++++++++needs to re attempt+++++++++++++log_ai_1.2+++++++++++++")
            aiResponse =askAi(messageThread,all_question)

        print("+++++++++++++++++++aiResponse+++++++++++++++++++++++")
        print(type(aiResponse))
        print(aiResponse.keys())
        print(aiResponse["reply_message"])
        
        if aiResponse["flag_kill_thread"] == True:
            continue
        replyTxtBox=messanger_container.find_element(By.CLASS_NAME, "send-textarea")
        try:
            replyTxtBox.click()
            print("*******************************")
            
            
            print(aiResponse["reply_message"])
            print(":::::::::::::::::::::::::::::::reply_message::::::::::::::::::::::::::::")
            
            
            lines = aiResponse["reply_message"].splitlines()
            # Iterate through each line and send it to the chat box
            for line in lines:
                replyTxtBox.send_keys(line)  # Send the line
                replyTxtBox.send_keys(Keys.ENTER) 

            print("wait for button")
            time.sleep(3)
            print("wait completed for button")
            # replyTxtBox.send_keys(Keys.ENTER)
            # random_sleep(4,6)
        except Exception as e:
            print(e)
        try:
            sellerData[current_supplier_name_txt]=aiResponse["extracted_answers"]
            savePklFIle(chat_dict_loc,sellerData)
            current_products = read_pickle_file(current_products_loc)
            currentProductName=getProductName(current_products,current_supplier_name_txt)
            
            supplierIndex=current_products[currentProductName]['suppliers'].index(current_supplier_name_txt)

            current_products[currentProductName]['suppliers'][supplierIndex] ={}
            current_products[currentProductName]['suppliers'][supplierIndex]=aiResponse["extracted_answers"]
            current_products[currentProductName]['flag_search_completed']=aiResponse["flag_kill_thread"]
            

            savePklFIle(current_products_loc,current_products)
        except Exception as e:
            print(e)


        # break loop for testing 
        # break


    # close the browser and complete the script
    driver.quit()



    # time.sleep(400)




# load_monitor()


# Schedule the function to run every 5 minutes
schedule.every(3).minutes.do(load_monitor)

# Record the start time
start_time = time.time()

while True:
    # Check if 50 minutes (3000 seconds) have passed
    elapsed_time = time.time() - start_time
    if elapsed_time > 30 * 60:  # 30 minutes in seconds
        print("Terminating the triggers after 50 minutes.")
        break  # Exit the loop and terminate the script

    # Run the scheduled tasks
    schedule.run_pending()
    time.sleep(1)  # wait for 1 second