import re
with open("src/App.tsx", "r") as f:
    content = f.read()

# I will write the whole file to make it cleaner and avoid diff issues.
