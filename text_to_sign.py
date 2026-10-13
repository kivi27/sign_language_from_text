
#!/usr/bin/env python3
"""
Text to Sign Language (ASL image lookup).

Image lookup priority:
1. Complete phrase image
2. Individual word image
3. Individual letter images

Folder structure:
text_to_sign/
    text_to_sign.py
    signs/
        a.png
        b.png
        ...
        z.png
        hello.png
        thank.png
        you.png
        thank you.png
        how are you.png

Install:
    python -m pip install pillow

Usage:
    python text_to_sign.py
    python text_to_sign.py "thank you"
    python text_to_sign.py "hello world" -o output.png
    python text_to_sign.py "how are you" --cols 5
"""

import argparse
import re
import string
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

SIGNS_DIR = Path(__file__).resolve().parent / "signs"

CELL_W = 180
CELL_H = 150
LABEL_H = 45
PAD = 10
ROW_GAP = 15
DEFAULT_COLS = 6


# --------------------------------------------------
# TEXT NORMALIZATION
# --------------------------------------------------

def normalize_text(text):
    """Normalize text for matching image filenames."""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        ch for ch in text
        if not unicodedata.combining(ch)
    )

    text = text.lower()

    # Convert punctuation to spaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove extra spaces.
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------
# LOAD AN IMAGE WHEN REQUIRED
# --------------------------------------------------

def load_image(path):
    """Load one PNG image and place transparency on white."""

    with Image.open(path) as source:
        image = source.convert("RGBA")

    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image)

    image = background.convert("RGB")
    image.thumbnail((CELL_W, CELL_H))

    return image


def find_image(key):
    """
    Find a PNG file by its name.

    Examples:
        hello       -> signs/hello.png
        thank you   -> signs/thank you.png
        a           -> signs/a.png

    Returns the image if found, otherwise None.
    """

    path = SIGNS_DIR / f"{key}.png"

    if not path.is_file():
        return None

    try:
        return load_image(path)
    except (OSError, ValueError) as exc:
        print(f"Warning: Could not read {path.name}: {exc}")
        return None


# --------------------------------------------------
# MATCH PHRASES, WORDS, AND LETTERS
# --------------------------------------------------

def parse_text(text):
    """
    Search the dataset before splitting words into letters.

    Priority:
        1. Longest matching phrase
        2. Individual word image
        3. Individual letter images

    Only the selected images are loaded.
    """

    normalized = normalize_text(text)

    if not normalized:
        return [], []

    words = normalized.split()
    items = []
    ignored = []

    index = 0

    while index < len(words):
        phrase_found = False

        # STEP 1:
        # Try the longest possible phrase first.
        #
        # Example:
        # "how are you" -> how are you.png
        # If missing, try "how are.png", then "how.png".

        for end in range(len(words), index, -1):
            phrase = " ".join(words[index:end])
            image = find_image(phrase)

            if image is not None:
                items.append((image, phrase.upper()))
                index = end
                phrase_found = True
                break

        if phrase_found:
            continue

        # STEP 2:
        # If no phrase matches, check the individual word.

        word = words[index]
        word_image = find_image(word)

        if word_image is not None:
            items.append((word_image, word.upper()))

        else:
            # STEP 3:
            # If the word image is unavailable, load letters.

            for char in word:
                letter_image = find_image(char)

                if letter_image is not None:
                    items.append((letter_image, char.upper()))
                elif char not in ignored:
                    ignored.append(char)

        index += 1

    return items, ignored


# --------------------------------------------------
# FONT
# --------------------------------------------------

def get_font(size=16):
    """Load a font available on Windows, macOS, or Linux."""

    candidates = []

    if sys.platform == "win32":
        candidates.extend([
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
        ])

    elif sys.platform == "darwin":
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ])

    candidates.extend([
        "arial.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
    ])

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue

    return ImageFont.load_default()


# --------------------------------------------------
# RENDER RESULT
# --------------------------------------------------

def render(text, cols=DEFAULT_COLS):
    """Create a combined image containing the matching sign images."""

    if cols < 1:
        raise ValueError("Columns must be at least 1.")

    if not SIGNS_DIR.is_dir():
        raise FileNotFoundError(
            f"Signs folder not found: {SIGNS_DIR}"
        )

    items, ignored = parse_text(text)

    if not items:
        raise ValueError(
            "No sign images found. Check your input and signs folder."
        )

    font = get_font()
    cell_h = CELL_H + LABEL_H

    # Calculate image positions.
    placements = []
    max_width = PAD

    for i, (image, label) in enumerate(items):
        row = i // cols
        col = i % cols

        x = PAD + col * (CELL_W + PAD)
        y = PAD + row * (cell_h + ROW_GAP)

        placements.append((x, y, image, label))
        max_width = max(max_width, x + CELL_W)

    rows = (len(items) + cols - 1) // cols
    canvas_width = max_width + PAD
    canvas_height = PAD + rows * cell_h + (rows - 1) * ROW_GAP + PAD

    canvas = Image.new(
        "RGB",
        (canvas_width, canvas_height),
        "white"
    )

    draw = ImageDraw.Draw(canvas)

    for x, y, image, label in placements:
        image_x = x + (CELL_W - image.width) // 2
        image_y = y + (CELL_H - image.height) // 2

        canvas.paste(image, (image_x, image_y))

        # Wrap long labels to fit inside the cell.
        max_label_width = CELL_W - 8
        lines = []
        current = ""

        for word in label.split():
            candidate = f"{current} {word}".strip()

            if (
                current
                and draw.textbbox((0, 0), candidate, font=font)[2]
                > max_label_width
            ):
                lines.append(current)
                current = word
            else:
                current = candidate

        if current:
            lines.append(current)

        label_y = y + CELL_H + 3

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]

            draw.text(
                (x + (CELL_W - text_width) // 2, label_y),
                line,
                fill="black",
                font=font,
            )

            label_y += 18

    return canvas, ignored


# --------------------------------------------------
# GUI
# --------------------------------------------------

def run_gui():
    """Launch the desktop application."""

    import tkinter as tk
    from tkinter import filedialog, messagebox
    from PIL import ImageTk

    root = tk.Tk()
    root.title("Text to Sign Language - ASL")
    root.geometry("1000x700")
    root.minsize(650, 450)

    # Input controls.
    top = tk.Frame(root)
    top.pack(fill="x", padx=12, pady=12)

    entry = tk.Entry(top, font=("Arial", 15))
    entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    entry.focus_set()

    # Scrollable image display.
    body = tk.Frame(root)
    body.pack(fill="both", expand=True, padx=12)

    canvas = tk.Canvas(
        body,
        bg="white",
        highlightthickness=0
    )

    vertical_scroll = tk.Scrollbar(
        body,
        orient="vertical",
        command=canvas.yview
    )

    horizontal_scroll = tk.Scrollbar(
        body,
        orient="horizontal",
        command=canvas.xview
    )

    canvas.configure(
        yscrollcommand=vertical_scroll.set,
        xscrollcommand=horizontal_scroll.set
    )

    vertical_scroll.pack(side="right", fill="y")
    horizontal_scroll.pack(side="bottom", fill="x")
    canvas.pack(side="left", fill="both", expand=True)

    status = tk.Label(
        root,
        text="Enter text and click Convert.",
        anchor="w"
    )
    status.pack(fill="x", padx=12, pady=8)

    state = {
        "image": None,
        "photo": None,
    }

    def convert(_event=None):
        text = entry.get().strip()

        if not text:
            messagebox.showwarning(
                "Empty Input",
                "Please enter some text."
            )
            return

        try:
            image, ignored = render(text)

        except (ValueError, FileNotFoundError, OSError) as exc:
            messagebox.showerror("Conversion Error", str(exc))
            return

        state["image"] = image
        state["photo"] = ImageTk.PhotoImage(image)

        canvas.delete("all")

        canvas.create_image(
            0,
            0,
            anchor="nw",
            image=state["photo"]
        )

        canvas.configure(
            scrollregion=(0, 0, image.width, image.height)
        )

        if ignored:
            status.config(
                text="Unsupported characters: " + ", ".join(ignored)
            )
        else:
            status.config(text="Conversion completed successfully.")

    def save():
        if state["image"] is None:
            messagebox.showinfo(
                "Nothing to Save",
                "Convert some text first."
            )
            return

        path = filedialog.asksaveasfilename(
            title="Save Sign Image",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            initialfile="sign_output.png"
        )

        if not path:
            return

        try:
            state["image"].save(path)
            status.config(text=f"Saved: {path}")

        except OSError as exc:
            messagebox.showerror("Save Error", str(exc))

    tk.Button(
        top,
        text="Convert",
        command=convert,
        font=("Arial", 11)
    ).pack(side="left", padx=(0, 8))

    tk.Button(
        top,
        text="Save PNG",
        command=save,
        font=("Arial", 11)
    ).pack(side="left")

    root.bind("<Return>", convert)
    root.mainloop()


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert text into sign language images."
    )

    parser.add_argument(
        "text",
        nargs="*",
        help="Text to convert. Leave empty to open the GUI."
    )

    parser.add_argument(
        "-o",
        "--output",
        default="sign_output.png",
        help="Output PNG filename."
    )

    parser.add_argument(
        "--cols",
        type=int,
        default=DEFAULT_COLS,
        help="Maximum number of images per row."
    )

    args = parser.parse_args()

    if not args.text:
        try:
            run_gui()
            return 0
        except ImportError as exc:
            print(f"Could not launch GUI: {exc}")
            return 1

    try:
        image, ignored = render(
            " ".join(args.text),
            args.cols
        )

        image.save(args.output)

    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Saved image: {args.output}")

    if ignored:
        print("Unsupported characters: " + ", ".join(ignored))

    return 0


if __name__ == "__main__":
    sys.exit(main())
