import pickle


def clear_pickle_file(file_path):
    try:
        # Read the original data
        with open(file_path, 'rb') as file:
            original_data = pickle.load(file)
            print(f"Original Data: {original_data}")

        # Create a blank object (you can customize this as needed)
        blank_data = {}

        # Save the blank object back to the pickle file
        with open(file_path, 'wb') as file:
            pickle.dump(blank_data, file)

        print("The pickle file has been cleared and a blank object has been saved.")
    except Exception as e:
        print(f"An error occurred: {e}")

# clear_pickle_file("chat_product_dict.pkl")
# clear_pickle_file("chat_step_dict.pkl")

def read_pickle_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            data = pickle.load(file)
            print(data)
    except Exception as e:
        print(f"An error occurred while reading the pickle file: {e}")

# Replace 'your_pickle_file.pkl' with the path to your pickle file
read_pickle_file("chat_product_dict.pkl")
read_pickle_file("chat_step_dict.pkl")



