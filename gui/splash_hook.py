import tkinter
from mozregression import version

win = tkinter.Tk()
tkinter.Label(win, text=f"mozregression {version} starting, please wait...").pack(pady=20, padx=20)

# Though the window is destroyed after 1 second, it persists until the
# bootloader is finished. This is hacky but seems to work.
win.after(1000, lambda: win.destroy())
win.overrideredirect(True)
win.eval("tk::PlaceWindow . center")
win.mainloop()
