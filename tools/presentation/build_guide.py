"""Create the beginner macOS presentation guide using the captured interface."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle, KeepTogether

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/pdf/Mac_Frontend_Demo_Guide.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
NAVY = colors.HexColor("#102638")
TEAL = colors.HexColor("#087f83")
INK = colors.HexColor("#243a4b")
MUTED = colors.HexColor("#587080")
PALE = colors.HexColor("#edf5f6")
GOLD = colors.HexColor("#f2b94b")
W, H = A4
WIDTH = W - 88

S = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10.2, leading=14.7, textColor=INK, spaceAfter=8),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, leading=12, textColor=MUTED, spaceAfter=7),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=NAVY, spaceAfter=14),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=18, textColor=TEAL, spaceBefore=9, spaceAfter=6),
    "cover": ParagraphStyle("cover", fontName="Helvetica-Bold", fontSize=38, leading=41, textColor=NAVY, spaceAfter=17),
    "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=9, leading=13, textColor=TEAL, spaceAfter=12),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=9.3, leading=15, textColor=NAVY, backColor=PALE,
                           borderPadding=10, spaceBefore=5, spaceAfter=14),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=9.1, leading=12.7, textColor=INK),
    "cellhead": ParagraphStyle("cellhead", fontName="Helvetica-Bold", fontSize=9, leading=12.5, textColor=colors.white),
}

story = []
def p(text, style="body"):
    return Paragraph(text, S[style])
def add(text, style="body"):
    story.append(p(text, style))
def code(*lines):
    add("<br/>".join(escape(x).replace(" ", "&#160;") for x in lines), "code")
def step(number, title, text):
    story.append(KeepTogether([p(f"{number:02d} / {title}", "h2"), p(text)]))
def image(name, width=WIDTH, max_height=280):
    from PIL import Image as PILImage
    path = ROOT / "docs/images" / name
    with PILImage.open(path) as im:
        w, h = im.size
    k = min(width / w, max_height / h)
    return Image(str(path), w * k, h * k, hAlign="LEFT")
def table(rows, widths, headers):
    content = [[p(x, "cellhead") for x in headers]] + [[p(x, "cell") for x in row] for row in rows]
    t = Table(content, colWidths=widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, colors.white]),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEAL),
    ]))
    story.append(t)
def new_page(kicker, title):
    story.append(PageBreak())
    add(kicker, "label")
    add(title, "h1")

add("PROJECT PRESENTATION / MAC EDITION", "label")
add("Show the rover<br/>website on a Mac.", "cover")
add("A beginner's setup and walkthrough guide", "h2")
add("For presenting the frontend alongside your project report and research paper. Run the website locally with sample data; no Raspberry Pi, rover, Python or camera connection is needed.")
story.append(Spacer(1, 8))
story.append(image("dashboard.png", max_height=285))
add("Actual interface screenshot in PRESENTATION DEMO mode. All displayed readings are sample data.", "small")
story.append(Spacer(1, 8))
table([["Install once", "Node.js LTS + project ZIP + npm ci"], ["Open the demo", "npm run demo, then the Local URL in your browser"], ["Present", "Dashboard > Manual control > Grid plan > Mission > Sensors"]], [112, WIDTH-112], ["YOUR ROUTE", "WHAT TO DO"])
story.append(Spacer(1, 10))
add("Keep this PDF open while following the steps. Commands are meant to be copied one line at a time; do not type the explanatory text around them.", "small")

new_page("01 / FIRST-TIME SETUP", "Install and open the project")
step(1, "Install Node.js LTS", 'Open <link href="https://nodejs.org/en/download" color="#087f83">nodejs.org/en/download</link>. Choose the <b>LTS macOS installer (.pkg)</b> and complete the installer. npm is included. In Apple menu > About This Mac, a listed Apple chip means <b>Apple Silicon / ARM64</b>; an Intel processor means <b>Intel / x64</b>. You do not need Homebrew.')
step(2, "Check that installation worked", "Press <b>Command + Space</b>, type <b>Terminal</b>, then press Return. Type these commands and press Return after each. Both should print version numbers. If not, close Terminal and open it again.")
code("node -v", "npm -v")
step(3, "Download and unzip the repository", 'Open <link href="https://github.com/AnshadityaSharma/pjt-1" color="#087f83">github.com/AnshadityaSharma/pjt-1</link>. Click the green <b>Code</b> button, then <b>Download ZIP</b>. In Finder > Downloads, double-click the ZIP if it was not extracted automatically. The usual folder name is <b>pjt-1-main</b>. This method does not require Git or a GitHub account for a public repository.')
step(4, "Move Terminal into the frontend folder", "If the extracted folder is in Downloads with its original name, copy this command. The folder name and the hyphens must match exactly.")
code("cd ~/Downloads/pjt-1-main/frontend")
add('<b>Folder in a different place?</b> In Terminal, type <font face="Courier">cd </font> (including the space), drag the <b>frontend</b> folder from Finder into Terminal, then press Return. Run <font face="Courier">pwd</font> if you want to check the location.', "small")
step(5, "Install the website's packages", "While still in the frontend folder, run the command below. Keep your internet connection on and let it finish. This downloads the packages listed by the project; it is needed once per fresh download.")
code("npm ci")
add("Do not open index.html directly in Finder. The application needs its local web server. Continue on the next page after npm ci finishes.", "small")

new_page("02 / RUNNING THE WEBSITE", "Start, reopen and stop")
add("In the same Terminal window, inside the frontend folder:")
code("npm run demo")
add('Your browser should open automatically. Otherwise, open Safari or Chrome and type <b>http://localhost:5173</b>. If Terminal prints another port, use that exact <b>Local</b> URL. This address points to your own laptop, not to a public website.')
add("Look for the violet PRESENTATION DEMO banner. Leave Terminal open while presenting; the running process is the local server.")
left = [p("Next time", "h2"), p("You do not need to reinstall packages on every visit. Open Terminal and run:"),
        p("cd ~/Downloads/pjt-1-main/frontend<br/>npm run demo", "code"),
        p("Stop the server", "h2"), p("Click Terminal and press <b>Control + C</b>. This is Control, not Command. Closing the browser tab alone does not stop the server."),
        p("Reset the presentation", "h2"), p("Reload the browser page. Sample missions, calibration edits, arming and other presentation state return to their initial values."),
        p("Camera note", "h2"), p("The camera panel shows a labelled sample still image. It is not a live camera feed.")]
right = [image("manual-panel.png", width=218, max_height=375), p("Touch-friendly manual controls. These change sample outputs only in this mode.", "small")]
t = Table([[left, right]], colWidths=[WIDTH-234, 234], hAlign="LEFT")
t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 12)]))
story.append(t)
add("For a quick demonstration, use npm run demo. npm run dev is the separate full-backend workflow and will wait for a Python backend if one is not running.", "small")

new_page("03 / WHAT THE FRONTEND HAS", "Know what each screen does")
add("The normal application supports the functions below. Browser presentation mode uses sample data and simplified interactions; it does not run the Python planner or control hardware.")
table([
    ["Dashboard", "Safety/arming, mission overview, localization, sensor health, camera and events.", "Sample cards and status."],
    ["Manual remote control", "Touch buttons, diagonals, joystick, arrows/WASD, speed limit and stop.", "Interactive sample outputs; no motors."],
    ["Grid planner", "Rectangle dimensions, m/cm/mm, spacing, margins, start corner, lane direction, pivot/arc turns.", "Simplified rectangle sketch; choose Pivot."],
    ["GPS planner / origin", "Map boundaries, device GPS or manual origin, bearing and geographic route display.", "Explore forms/map. Polygon route generation and projection need the backend."],
    ["Mission", "Save/load, start, pause, resume, stop, progress, elapsed time and route trace.", "Grid mission animation, not physics."],
    ["History", "Mission records, outcomes, timeline, review notes and detections.", "Sample and session-created records; reload resets them."],
    ["Sensors", "Readings, connection state, validity, age, calibration and optional device status.", "Illustrative sensor values."],
    ["Camera / detection", "Camera sources, model/inference status, candidate events, saved snapshots and alerts.", "Labelled still; no actual YOLO inference or live detections."],
    ["System / Connection", "Faults, configuration, calibration, simulator controls, backend URL and token.", "Browse status; sample calibration only. Real connections, exports and fault injection are unavailable."],
    ["Emergency stop", "Large red, persistent E-stop with an explicit reset workflow.", "Latches the sample UI state only."],
], [106, 223, WIDTH-329], ["SCREEN", "PROJECT FUNCTION", "IN THIS DEMO"])
story.append(Spacer(1, 10))
add("An unavailable GPS or disabled detector is a truthful status, not a failed presentation. Explain that those functions need their actual data source or the full simulator.", "small")

new_page("04 / A FIVE-MINUTE TOUR", "A clear presentation sequence")
story.append(image("route-preview.png", max_height=220))
add("A 5 x 5 m browser preview. Boustrophedon coverage uses alternating back-and-forth survey lanes.", "small")
step(1, "Dashboard - introduce the console", "Point out the presentation banner and explain that the dashboard combines safety, mission and sensor information. The displayed readings are examples.")
step(2, "Manual - show the operator controls", "Open Manual Remote Control. Choose Take manual control, then Arm (simulated). Hold Forward or an arrow key and release it. Show the speed slider, Stop and joystick. Click Release before moving to autonomous controls.")
step(3, "Planner - explain the coverage pattern", "Open Autonomous Boustrophedon. Click Quick 5m x 5m Demo Box. Change lane spacing or dimensions and show the sketch update. Keep Pivot selected. Explain margins, start corner and estimated duration; browser totals are indicative.")
step(4, "Mission - show the workflow", "Click Save &amp; load mission. If needed, Arm (simulated), then Start mission. Show the progress animation, Pause and Resume. This demonstrates the interface flow, not measured vehicle motion.")
step(5, "Sensors, camera and E-stop - close the tour", "Show the sample sensor values and the labelled camera still. Explain that real candidate detection needs trained weights and a camera. Finish by pressing E-STOP. Reset it afterwards, or reload the page for a fresh presentation.")
add("Suggested wording", "h2")
add('"This is the browser-only presentation mode. It demonstrates the operator interface with sample data. The real planner, sensor processing, camera inference and motor control run in the separate backend."')

new_page("05 / HELP & PRESENTATION CHECKLIST", "If something does not work")
table([
    ["node or npm: command not found", "Finish installing Node.js LTS, close Terminal, reopen it and retry node -v / npm -v."],
    ["No such file or directory", "The ZIP folder has a different name or location. Type cd followed by a space, drag the frontend folder into Terminal and press Return."],
    ["ENOENT / package.json missing", "You are in the wrong folder. Use the frontend folder, not the project root or the ZIP file."],
    ["npm ci cannot download", "Check internet access, a restrictive campus proxy or VPN. Retry after fixing connectivity. Do not use sudo or delete the lockfile as a first step."],
    ["Loading / backend offline", "Stop the server with Control + C, run npm run demo and use its printed URL. Confirm that the presentation banner is visible."],
    ["Address busy / browser does not open", "Use the exact Local URL printed by Vite; it may choose 5174 or another free port. Keep Terminal running."],
    ["Map blank / GPS refused", "Map tiles need internet. Browser GPS also needs permission and a supported secure context. Use the local Grid plan sketch; no GPS is needed for this presentation."],
    ["Controls do not start", "In Manual, take control and arm the sample rover. For a mission, release manual control first. If E-stop is latched, reset it. Reload to start fresh."],
], [150, WIDTH-150], ["WHAT YOU SEE", "WHAT TO DO"])
story.append(Spacer(1, 9))
add("Before meeting the guide", "h2")
add("Install packages and launch the demo in advance. Keep this PDF, the report and the research paper ready. Plug in the laptop, zoom the browser to a comfortable size, test the manual/grid workflow and keep Terminal open. After installation, the core demo can run without internet; online map tiles may be absent.")
add("What this demonstration does not establish", "h2")
add("Sample readings, route animation and camera stills do not establish hardware performance, mine detection accuracy or safe terrain. A GPS anchor is not continuous rover tracking. The physical E-stop and power cut-off must be verified on hardware.", "small")
add('Project: <link href="https://github.com/AnshadityaSharma/pjt-1" color="#087f83">github.com/AnshadityaSharma/pjt-1</link><br/>Official setup references: <link href="https://nodejs.org/en/download" color="#087f83">Node.js downloads</link> and <link href="https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository" color="#087f83">GitHub repository download/clone help</link>.<br/>Screenshots: this project, captured in browser presentation mode. Guide prepared 20 October 2026.', "small")

def chrome(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, H-9, W, 9, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(44, H-31, "SURVEY ROVER  /  FRONTEND PRESENTATION")
    canvas.setStrokeColor(colors.HexColor("#d8e4e9"))
    canvas.line(44, 38, W-44, 38)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(44, 24, "macOS guide  |  Browser-only sample data  |  No rover required")
    canvas.drawRightString(W-44, 24, f"{doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=57, bottomMargin=49,
    title="Survey Rover - Mac Frontend Demo Guide", author="Survey Rover Project", subject="Beginner macOS setup and frontend feature walkthrough")
doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
print(OUT)
