from mozregression import version
import multiprocessing as mp
import os
import subprocess


class Splash:
    # Milliseconds to pass before re-checking open files.
    CHECK_MILLISECONDS = 3000

    def __init__(self):
        # Must import here to avoid multiprocess forking issue with Core Foundation.
        import tkinter

        # Get parent PID which will be the one extracting files, etc...
        self.ppid = str(os.getppid())

        # Variable to keep track of last lsof output.
        self.last_lsof = None

        # Create the splash screen.
        self.win = tkinter.Tk()
        self.win.overrideredirect(True)
        self.win.eval("tk::PlaceWindow . center")
        tkinter.Label(self.win, text=f"mozregression {version} starting, please wait...").pack(
            pady=20, padx=20
        )
        self.win.after(self.CHECK_MILLISECONDS, self.check_doneness)
        self.win.mainloop()

    def check_doneness(self):
        """Check whether the bootloader has finished loading files."""

        # NOTE: This is a bit hacky. The output from lsof is checked every few seconds
        # and if it has not changed between those two checks, assume extraction is
        # complete.

        out = subprocess.check_output(["lsof", "-p", self.ppid])
        if not self.last_lsof:
            self.last_lsof = out
        if out == self.last_lsof:
            self.win.destroy()
        else:
            self.win.after(self.CHECK_MILLISECONDS, self.check_doneness)


def splash():
    """Create a Splash instance."""
    Splash()


if __name__ == "__main__":
    mp.freeze_support()
    mp.set_start_method("fork")
    p = mp.Process(target=splash, args=())
    p.start()
