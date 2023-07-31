import tkinter

if __name__ == "__main__":
    win = tkinter.Tk()
    win.eval("tk::PlaceWindow . center")
    win.overrideredirect(True)
    tkinter.Label(win, text="mozregression is starting, please wait...").pack(pady=20, padx=20)
    win.after(1000, lambda: win.destroy())
    win.mainloop()
