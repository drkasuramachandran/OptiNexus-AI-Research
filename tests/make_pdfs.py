import fitz

DOCS = {
    "fbg_strain_sensor.pdf": [
        ("High-Sensitivity Fibre Bragg Grating Strain Sensor\nA. Rivera, K. Osei\nJournal of Test Photonics, 2021\n\nAbstract\nWe report a fibre Bragg grating (FBG) strain sensor interrogated at 1550 nm.\n\n1. Introduction\nStrain monitoring in composite structures requires compact sensors. The problem addressed is low strain sensitivity of bare FBGs.\nThe objective is to double the strain sensitivity using a polymer coating."),
        ("2. Experimental setup\nA broadband ASE source (1520-1570 nm) and an optical spectrum analyser (Yokogawa AQ6370) were used. The grating length was 10 mm.\n\n3. Results\nThe measured strain sensitivity was 2.4 pm/microstrain, compared with 1.2 pm/microstrain for the bare grating. Temperature cross-sensitivity was 10 pm/C.\n\n4. Conclusions\nPolymer coating doubled the strain sensitivity. Limitations include temperature cross-sensitivity. Future work will add temperature compensation."),
    ],
    "mzi_temperature_sensor.pdf": [
        ("Mach-Zehnder Interferometric Fibre Temperature Sensor\nL. Chen, M. Novak\nTest Optics Letters, 2023\n\nAbstract\nAn in-line Mach-Zehnder interferometer (MZI) based on core-offset splicing is demonstrated for temperature sensing.\n\n1. Introduction\nThe problem is achieving high temperature sensitivity with low-cost fabrication."),
        ("2. Methods\nTwo core-offset splices separated by 30 mm form the interferometer. The setup used a superluminescent diode at 1310 nm and a tunable laser.\n\n3. Results\nThe interference dip shifted with a temperature sensitivity of 85 pm/C over 25-100 C with linearity R2 = 0.998.\n\n4. Conclusions\nThe MZI offers higher temperature sensitivity than FBG-based sensors. Strain cross-talk was not evaluated."),
    ],
}

for name, pages in DOCS.items():
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 800), text, fontsize=11)
    doc.save(f"/app/tests/{name}")
print("ok")
