# Mobile App Icons

> Created: 2026-04-15

Workflow to generate all Android launcher icons from a single SVG source file. The icon lives at `assets/icon.svg`. All sizes are generated from a 1024×1024 PNG exported from that file.

Step 1 — Export the SVG as a 1024×1024 PNG

The confirmed working method is Inkscape:

1. Open `assets/icon.svg` in Inkscape
2. Go to File → Export PNG Image (or Ctrl+Shift+E)
3. Under the Page tab, set width and height to 1024×1024
4. Set the export path to `assets/icon.png` inside your project folder
5. Click Export

Other tools that can do the same conversion:

- GIMP — File → Open SVG → set 1024×1024 canvas → Export as PNG
- Figma (browser) — Import SVG → right-click → Export → PNG at 1x (set frame to 1024×1024)
- Canva (browser) — Upload SVG → resize to 1024×1024 → Download as PNG

Step 2 — Run the generator

```
flutter pub get
dart run flutter_launcher_icons
```

All Android icon sizes are generated automatically in `android/app/src/main/res/`.

- [[flutter-launcher-icons]]
