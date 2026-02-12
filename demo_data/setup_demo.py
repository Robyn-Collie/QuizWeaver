"""
Demo Data Setup Script for QuizWeaver Workshop

This script populates the database with demo classes and lessons for the workshop presentation.

Usage:
    python demo_data/setup_demo.py

The script will:
- Initialize the database schema (run migrations)
- Create 2 demo classes (7th Grade Science, 8th Grade Earth Science)
- Log 3-4 sample lessons to those classes
- Print progress and summary

Note: This script is idempotent - it will skip creating classes/lessons if they already exist.
"""

import os
import sys
from datetime import date

# Add project root to sys.path so imports work from any directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.classroom import create_class
from src.database import get_engine, get_session
from src.lesson_tracker import log_lesson
from src.migrations import init_database_with_migrations


def setup_demo_data():
    """
    Set up demo data for QuizWeaver workshop presentation.

    Creates demo classes and logs sample lessons to demonstrate the platform.
    """
    db_path = "quiz_warehouse.db"

    print("\n=== QuizWeaver Demo Data Setup ===\n")

    # Step 1: Initialize database
    print("[1/4] Initializing database...")
    try:
        init_database_with_migrations(db_path)
        print("      [OK] Database schema initialized\n")
    except Exception as e:
        print(f"      [FAIL] Database initialization failed: {e}")
        return False

    # Step 2: Create database connection
    print("[2/4] Connecting to database...")
    try:
        engine = get_engine(db_path)
        session = get_session(engine)
        print("      [OK] Database connection established\n")
    except Exception as e:
        print(f"      [FAIL] Database connection failed: {e}")
        return False

    # Step 3: Create demo classes
    print("[3/4] Creating demo classes...")
    classes_created = []

    try:
        # Class 1: 7th Grade Science - Block A
        class1 = create_class(
            session=session,
            name="7th Grade Science - Block A",
            grade_level="7th Grade",
            subject="Science",
            standards=["SOL 7.1", "SOL 7.2", "SOL 7.3"],
        )
        session.commit()
        classes_created.append(class1)
        print(f"      [OK] Created class: {class1.name} (ID: {class1.id})")

        # Class 2: 8th Grade Earth Science
        class2 = create_class(
            session=session,
            name="8th Grade Earth Science",
            grade_level="8th Grade",
            subject="Earth Science",
            standards=["SOL 8.1", "SOL 8.2"],
        )
        session.commit()
        classes_created.append(class2)
        print(f"      [OK] Created class: {class2.name} (ID: {class2.id})\n")

    except Exception as e:
        print(f"      [FAIL] Class creation failed: {e}")
        session.rollback()
        session.close()
        engine.dispose()
        return False

    # Step 4: Log demo lessons
    print("[4/4] Logging demo lessons...")
    lessons_logged = {class1.id: 0, class2.id: 0}

    try:
        # Lesson 1 for Class 1: Photosynthesis
        lesson1 = log_lesson(
            session=session,
            class_id=class1.id,
            content="""Photosynthesis: The Process of Food Production in Plants

Overview:
Plants produce their own food through photosynthesis, a chemical process that converts light energy into chemical energy stored in glucose.

Key Concepts:
- Photosynthesis equation: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2
- Chloroplasts contain chlorophyll, which absorbs light energy (mainly red and blue wavelengths)
- The process occurs in two stages: light-dependent reactions (in thylakoids) and light-independent reactions/Calvin cycle (in stroma)
- Factors affecting photosynthesis: light intensity, CO2 concentration, temperature, water availability

Activities:
- Lab: Observing chloroplasts under microscope
- Experiment: Testing factors that affect photosynthesis rate using Elodea plants
- Students measured oxygen bubble production under different light conditions""",
            topics=["photosynthesis", "chloroplasts", "light reactions", "Calvin cycle", "glucose production"],
            notes="Students struggled with understanding the difference between light-dependent and light-independent reactions. Need to review the flow of energy through both stages.",
            lesson_date=date(2026, 2, 3),
            standards_addressed=["SOL 7.1", "SOL 7.2"],
        )
        session.commit()
        lessons_logged[class1.id] += 1
        print(f"      [OK] Logged lesson: Photosynthesis (Class: {class1.name})")

        # Lesson 2 for Class 1: Cellular Respiration
        lesson2 = log_lesson(
            session=session,
            class_id=class1.id,
            content="""Cellular Respiration: Releasing Energy from Food

Overview:
All living cells break down glucose to release energy through cellular respiration, the reverse process of photosynthesis.

Key Concepts:
- Cellular respiration equation: C6H12O6 + 6O2 → 6CO2 + 6H2O + ATP energy
- Three stages: Glycolysis (cytoplasm), Krebs cycle (mitochondrial matrix), Electron transport chain (inner mitochondrial membrane)
- Aerobic vs. anaerobic respiration (fermentation)
- ATP is the energy currency of cells (approximately 36-38 ATP molecules per glucose)
- Mitochondria are the "powerhouses" of the cell

Activities:
- Yeast fermentation lab: Observing CO2 production with different sugar sources
- Diagram: Comparing photosynthesis and cellular respiration
- Discussion: Why do we breathe? Connecting respiration to everyday life

Assessment:
- Students completed a concept map showing the relationship between photosynthesis and cellular respiration""",
            topics=[
                "cellular respiration",
                "ATP",
                "mitochondria",
                "glycolysis",
                "Krebs cycle",
                "electron transport chain",
                "fermentation",
            ],
            notes="Strong understanding of the overall process. Some confusion about where each stage occurs in the cell. The yeast lab was very engaging - students loved seeing the balloons inflate from CO2 production.",
            lesson_date=date(2026, 2, 4),
            standards_addressed=["SOL 7.1", "SOL 7.3"],
        )
        session.commit()
        lessons_logged[class1.id] += 1
        print(f"      [OK] Logged lesson: Cellular Respiration (Class: {class1.name})")

        # Lesson 3 for Class 2: Water Cycle
        lesson3 = log_lesson(
            session=session,
            class_id=class2.id,
            content="""The Water Cycle: Earth's Water in Motion

Overview:
Water continuously moves between Earth's surface and atmosphere through evaporation, condensation, precipitation, and collection.

Key Concepts:
- Water cycle processes: evaporation, transpiration, condensation, precipitation, infiltration, runoff
- Energy from the Sun drives the water cycle
- Water changes state but the total amount remains constant (conservation of mass)
- Groundwater vs. surface water
- Human impact on the water cycle (urbanization, deforestation, climate change)

Virginia Connection:
- Chesapeake Bay watershed - largest estuary in the US
- James River, Potomac River, and their role in Virginia's water system
- Seasonal precipitation patterns in Virginia

Activities:
- Created water cycle diagrams with annotations
- Video: NASA visualization of global precipitation patterns
- Case study: How impervious surfaces in cities affect local water cycles

Discussion:
- Why is Virginia's water quality important for the Chesapeake Bay?
- How does the water cycle connect to weather and climate?""",
            topics=[
                "water cycle",
                "evaporation",
                "precipitation",
                "condensation",
                "infiltration",
                "runoff",
                "groundwater",
                "Chesapeake Bay",
            ],
            notes="Students had great prior knowledge from elementary school. Focused on the energy aspects and human impacts. Need to review the differences between weather and climate before our next unit.",
            lesson_date=date(2026, 2, 5),
            standards_addressed=["SOL 8.1"],
        )
        session.commit()
        lessons_logged[class2.id] += 1
        print(f"      [OK] Logged lesson: Water Cycle (Class: {class2.name})")

        # Lesson 4 for Class 1: Cell Structure and Function
        lesson4 = log_lesson(
            session=session,
            class_id=class1.id,
            content="""Cell Structure and Function: The Building Blocks of Life

Overview:
All living things are made of cells. Understanding cell structure helps us understand how organisms carry out life processes.

Key Concepts:
- Cell theory: All living things are made of cells, cells are the basic unit of life, all cells come from pre-existing cells
- Prokaryotic vs. Eukaryotic cells
- Plant vs. Animal cells (cell wall, chloroplasts, large central vacuole in plants)
- Major organelles and their functions:
  * Nucleus - genetic control center
  * Mitochondria - energy production
  * Chloroplasts - photosynthesis (plants only)
  * Ribosomes - protein synthesis
  * Endoplasmic reticulum - protein and lipid processing
  * Golgi apparatus - packaging and distribution
  * Cell membrane - selective barrier

Activities:
- Microscope lab: Observing onion cells (plant) and cheek cells (animal)
- Cell model project: Students created 3D models of plant or animal cells
- Analogy activity: Comparing cell organelles to parts of a factory or city

Key Vocabulary:
organelle, nucleus, mitochondria, chloroplast, cell membrane, cell wall, cytoplasm, ribosome""",
            topics=[
                "cell structure",
                "organelles",
                "cell theory",
                "plant cells",
                "animal cells",
                "microscopy",
                "prokaryotic",
                "eukaryotic",
            ],
            notes="Microscope lab went well! Most students successfully focused and saw cells. A few students still struggling with the concept that cells are three-dimensional, not flat like in diagrams. The cell model project is due next week - students are excited about getting creative.",
            lesson_date=date(2026, 2, 6),
            standards_addressed=["SOL 7.1"],
        )
        session.commit()
        lessons_logged[class1.id] += 1
        print(f"      [OK] Logged lesson: Cell Structure and Function (Class: {class1.name})\n")

    except Exception as e:
        print(f"      [FAIL] Lesson logging failed: {e}")
        session.rollback()
        session.close()
        engine.dispose()
        return False

    # Capture summary info before closing session (avoids DetachedInstanceError)
    summary_info = []
    for cls in classes_created:
        summary_info.append((cls.name, cls.id, lessons_logged.get(cls.id, 0)))
    total_lessons = sum(lessons_logged.values())

    # Close database connection
    session.close()
    engine.dispose()

    # Print summary
    print("=== Demo Data Setup Complete ===\n")
    print("Summary:")
    print(f"  - Classes created: {len(summary_info)}")
    for name, cid, lesson_count in summary_info:
        print(f"    * {name} (ID: {cid}) - {lesson_count} lesson(s) logged")
    print(f"\n  - Total lessons logged: {total_lessons}")
    print(f"\nDatabase: {db_path}")
    print("\nYou can now use these classes and lessons for your workshop presentation!")
    print("\nNext steps:")
    print("  - View classes: python main.py list-classes")
    print("  - View lessons: python main.py list-lessons --class-id <id>")
    print("  - Generate quiz: python main.py generate --class-id <id>\n")

    return True


if __name__ == "__main__":
    try:
        success = setup_demo_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
