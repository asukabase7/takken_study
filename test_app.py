import tkinter as tk
import sys
import os

# add to path
sys.path.insert(0, os.path.abspath('.'))

import gui.app as app_module

app = app_module.TakkenApp()
app.update()

# Test theme
app._toggle_theme()
app.update()

# Test check_answer
app.load_question()
app.update()
app.check_answer(0)
app.update()

print("ALL TESTS PASSED")
app.destroy()
