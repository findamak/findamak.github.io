#!/usr/bin/env python3
"""Rotate the daily exercises on Chiara and Cooper's learning pages.

The pages deliberately retain ES5 browser code for compatibility with an older iPad.
This updater only replaces each page's JSON exercise array.
"""

import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = {"chiara": ROOT / "chiara.html", "cooper": ROOT / "cooper.html"}


def choice(title, question, prompt, options, answer):
    return {"type": "choice", "title": title, "question": question,
            "prompt": prompt, "options": options, "answer": answer}


def input_answer(title, question, prompt, answer):
    return {"type": "input", "title": title, "question": question,
            "prompt": prompt, "answer": answer, "options": []}


# Chiara: 3 numeracy, 3 spelling, 2 grammar/punctuation, 2 reading/reasoning.
CHIARA_SETS = [
    [
        input_answer("Numeracy: Multiply", "What is 7 x 8?", "Think: 7 groups of 8.", ["56", "fifty six", "fifty-six"]),
        choice("Numeracy: Fractions", "Which fraction is equal to one half?", "Look for a fraction with the same-sized parts shaded.", ["2/4", "1/3", "3/8", "1/5"], "2/4"),
        choice("Numeracy: Money", "You have $10.00 and spend $3.75. How much is left?", "Subtract dollars, then cents.", ["$6.25", "$6.35", "$7.25", "$13.75"], "$6.25"),
        input_answer("Spelling: Sound Pattern", "Spell the word: a person who teaches a class.", "It starts with T and has 7 letters.", "teacher"),
        choice("Spelling: Choose Correctly", "Which spelling is correct?", "Say the word slowly: beautiful.", ["beautiful", "beutiful", "beautifull", "butiful"], "beautiful"),
        input_answer("Spelling: Tricky Word", "Spell the word that means necessary.", "It has double S in the middle.", "necessary"),
        choice("Grammar: Word Class", "Which word is a verb in this sentence: The puppy chased the ball?", "A verb is an action word.", ["puppy", "chased", "the", "ball"], "chased"),
        choice("Punctuation: Sentence End", "Which sentence has the correct punctuation?", "A question needs a question mark.", ["Where are my shoes?", "Where are my shoes.", "where are my shoes?", "Where are my shoes!"], "Where are my shoes?"),
        choice("Reading: Main Idea", "Read: Sam watered the seedlings every day. Soon, green shoots appeared. What is the main idea?", "Think about what the whole passage is mostly about.", ["Sam cared for plants", "Sam lost his shoes", "It was snowing", "Sam was late"], "Sam cared for plants"),
        input_answer("Reasoning: Pattern", "What comes next? 5, 10, 15, 20, __", "The pattern adds 5 each time.", ["25", "twenty five", "twenty-five"]),
    ],
    [
        input_answer("Numeracy: Divide", "What is 48 divided by 6?", "Think: 6 times what number equals 48?", ["8", "eight"]),
        choice("Numeracy: Place Value", "What is the value of the 6 in 4,682?", "Look at the hundreds place.", ["6", "60", "600", "6000"], "600"),
        input_answer("Numeracy: Time", "A movie begins at 2:35 and lasts 45 minutes. What time does it end?", "Add 25 minutes to reach 3:00, then 20 more.", ["3:20", "3.20", "three twenty"]),
        choice("Spelling: Choose Correctly", "Which spelling is correct?", "Listen for the -tion ending.", ["celebration", "celebrashun", "celebbration", "celebrationn"], "celebration"),
        input_answer("Spelling: Prefix", "Spell the word meaning not possible.", "It begins with im- and ends with -ible.", "impossible"),
        choice("Spelling: Homophones", "Which word completes the sentence? I can ___ the sea from here.", "Choose the word that means to look.", ["see", "sea", "sew", "say"], "see"),
        choice("Grammar: Nouns", "Which word is a noun in this sentence: The bright kite floated above the trees?", "A noun names a person, place, thing, or idea.", ["bright", "kite", "floated", "above"], "kite"),
        choice("Punctuation: Commas", "Which sentence uses commas correctly?", "Use commas to separate items in a list.", ["I packed apples, crackers, and cheese.", "I packed apples crackers, and cheese.", "I packed, apples crackers and cheese.", "I packed apples, crackers and, cheese."], "I packed apples, crackers, and cheese."),
        choice("Reading: Inference", "Read: Leo wore a coat, scarf, and gloves before leaving home. What can you infer?", "Use the clues in the sentence.", ["It was cold", "It was very hot", "Leo was swimming", "Leo was asleep"], "It was cold"),
        input_answer("Reasoning: Pattern", "What comes next? 2, 6, 18, 54, __", "Each number is multiplied by 3.", ["162", "one hundred sixty two", "one hundred and sixty two"]),
    ],
]

COOPER_SETS = [
    [
        choice("Letter Sounds", "Which word starts with the same sound as map?", "Listen: mmmmap.", ["moon", "sun", "fish", "cake"], "moon"),
        input_answer("Counting On", "What number comes after 14?", "Count forward: 12, 13, 14, ...", ["15", "fifteen"]),
        choice("Tiny Addition", "What is 5 + 2?", "Start at 5 and count on two.", ["6", "7", "8", "9"], "7"),
        choice("Take Away Toys", "You have 8 blocks and put 3 away. How many are left?", "Count back three from 8.", ["4", "5", "6", "7"], "5"),
        choice("Shape Hunt", "Which shape has four equal sides?", "Think about a square.", ["Circle", "Triangle", "Square", "Oval"], "Square"),
        input_answer("Missing Letter", "Finish the word: D O __", "It says dog. What letter is missing?", ["g", "G"]),
        choice("Pattern Builder", "What comes next? yellow, green, yellow, green, yellow", "The colours take turns.", ["yellow", "green", "blue", "red"], "green"),
        choice("More or Less", "Which number is less than 10?", "Less means smaller.", ["12", "14", "8", "11"], "8"),
        choice("Story Thinking", "Noah puts on his bathers and takes a towel. Where might he be going?", "Use the clues: bathers and towel.", ["Swimming", "To bed", "To the snow", "To the library"], "Swimming"),
        choice("Kind Choices", "A new child is sitting alone. What is a kind thing to do?", "Pick the friendly answer.", ["Invite them to play", "Point and laugh", "Hide their bag", "Ignore them"], "Invite them to play"),
    ],
    [
        choice("Letter Sounds", "Which word starts with the same sound as fish?", "Listen: ffffish.", ["fan", "sun", "moon", "cake"], "fan"),
        input_answer("Counting Back", "What number comes before 20?", "Count backwards: 20, ...", ["19", "nineteen"]),
        choice("Tiny Addition", "What is 3 + 4?", "Count on four from 3.", ["6", "7", "8", "9"], "7"),
        choice("Take Away Toys", "You have 10 stickers and give 4 away. How many are left?", "Count back four from 10.", ["5", "6", "7", "8"], "6"),
        choice("Shape Hunt", "Which shape is round with no corners?", "Think of a ball.", ["Square", "Triangle", "Circle", "Rectangle"], "Circle"),
        input_answer("Missing Letter", "Finish the word: S U __", "It says sun. What letter is missing?", ["n", "N"]),
        choice("Pattern Builder", "What comes next? clap, stomp, clap, stomp, clap", "The actions take turns.", ["clap", "stomp", "jump", "spin"], "stomp"),
        choice("More or Less", "Which number is more than 15?", "More means bigger.", ["12", "14", "16", "13"], "16"),
        choice("Story Thinking", "Ava puts seeds in soil and gives them water. What is she doing?", "Use the clues: seeds, soil, and water.", ["Planting", "Cooking", "Painting", "Sleeping"], "Planting"),
        choice("Kind Choices", "Your friend cannot find their hat. What should you do?", "Pick the helpful answer.", ["Help look for it", "Hide your hat", "Laugh", "Walk away"], "Help look for it"),
    ],
]


def replace_exercises(page, exercises):
    text = page.read_text(encoding="utf-8")
    replacement = "var exercises = " + json.dumps(exercises, indent=2, ensure_ascii=True) + ";"
    updated, count = re.subn(r"var exercises = \[.*?\];", replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not find unique exercises array in " + str(page))
    page.write_text(updated, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Rotation date YYYY-MM-DD (default: today)")
    parser.add_argument("--check", action="store_true", help="Print selected rotation without writing")
    args = parser.parse_args()
    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    index = day.toordinal()
    selected = {"chiara": CHIARA_SETS[index % len(CHIARA_SETS)],
                "cooper": COOPER_SETS[index % len(COOPER_SETS)]}
    for child, exercises in selected.items():
        if len(exercises) != 10:
            raise RuntimeError(child + " must have exactly 10 exercises")
        if not args.check:
            replace_exercises(PAGES[child], exercises)
        print(child + ": rotation " + str(index % len(exercises)) + ", " + str(len(exercises)) + " exercises")


if __name__ == "__main__":
    main()
