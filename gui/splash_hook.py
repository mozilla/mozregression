import multiprocessing as mp
import os
import subprocess

from mozregression import version


class Splash:
    # Milliseconds to pass before re-checking open files.
    CHECK_MILLISECONDS = 500

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
        tkinter.Label(self.win, text=f"mozregression {version} starting, please wait...").pack(
            pady=20, padx=20
        )
        self.win.eval("tk::PlaceWindow . center")
        self.win.after(self.CHECK_MILLISECONDS, self.check_doneness)
        self.win.mainloop()

    def get_lsof(self):
        """Return a list of files that are extracted by the bootloader."""
        out = subprocess.check_output(["lsof", "-p", self.ppid])
        lines = out.splitlines()

        # _MEI is the prefix used in the temporary folder when extracting. See
        # pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works.
        relevant_lines = [line for line in lines if b"_MEI" in line]

        # Return only the filenames.
        parsed_lines = [line.split(b" ")[-1] for line in relevant_lines]
        parsed_lines.sort()
        return parsed_lines

    def check_doneness(self):
        """Check whether the bootloader has finished loading files."""

        # NOTE: This is a bit hacky. The output from lsof is checked every few seconds
        # and if it has not changed between those two checks, assume extraction is
        # complete.

        parsed_lsof = self.get_lsof()
        if parsed_lsof == self.last_lsof:
            self.win.destroy()
        else:
            self.last_lsof = parsed_lsof
            self.win.after(self.CHECK_MILLISECONDS, self.check_doneness)


if __name__ == "__main__":
    mp.set_start_method("fork")
    p = mp.Process(target=Splash)
    p.start()
