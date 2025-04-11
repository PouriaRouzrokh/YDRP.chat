import re

pattern = re.compile(r'^(.+)_(\d{20})$')
test_folders = [
    'Test_Policy_12345678901234567890',
    'Test_With_Multiple_Underscores_12345678901234567890',
    'Invalid_Format_123'
]

for folder in test_folders:
    match = pattern.match(folder)
    print(f'Folder: {folder}')
    print(f'  Match: {bool(match)}')
    if match:
        print(f'  Groups: {match.groups()}')
    print() 