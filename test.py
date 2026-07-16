import numpy as np
imort pandas as pd

file_path = 'data.csv'

def load_data(file_path):
    data = pd.read_csv(file_path)
    return data

def main():
    data = load_data('data.csv')
    print(data.head())

if __name__ == '__main__':
    main()