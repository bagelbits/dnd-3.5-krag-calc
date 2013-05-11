#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
    Spell Database Populater
    Written by Christopher Durien Ward

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>
"""


import sqlite3
import traceback
import re
from sys import exit


def table_setup(name, db_cursor):
    if(name == 'spell'):
        db_cursor.execute("CREATE TABLE spell\
            (id INTEGER PRIMARY KEY, name TINYTEXT,\
            cast_time TINYTEXT, range TINYTEXT,\
            target TINYTEXT, effect TINYTEXT, area TINYTEXT, duration TINYTEXT,\
            saving_throw TINYTEXT, description TINYTEXT, components TINYTEXT)")

    elif(name == 'class'):
        db_cursor.execute("CREATE TABLE class (\
            id INTEGER PRIMARY KEY, name TINYTEXT,\
            probability INT, divine INT, arcane INT)")

    elif(name == 'spell_class'):
        db_cursor.execute("CREATE TABLE spell_class (\
            id INTEGER PRIMARY KEY, class_id INT,\
            spell_id INT, level INT, subtype TINYTEXT)")

    elif(name == 'domain'):
        db_cursor.execute("CREATE TABLE domain (\
            id INTEGER PRIMARY KEY, name TINYTEXT)")

    elif(name == 'spell_domain'):
        db_cursor.execute("CREATE TABLE spell_domain (\
            id INTEGER PRIMARY KEY, domain_id INT,\
            spell_id INTEGER, level INT)")

    elif(name == 'book'):
        db_cursor.execute("CREATE TABLE book (\
            id INTEGER PRIMARY KEY, name TINYTEXT)")

    elif(name == 'spell_book'):
        db_cursor.execute("CREATE TABLE spell_book (\
            id INTEGER PRIMARY KEY, book_id INT,\
            spell_id INT, page INT)")

    elif(name == 'school'):
        db_cursor.execute("CREATE TABLE school (\
            id INTEGER PRIMARY KEY, name TINYTEXT)")

    elif(name == 'spell_school'):
        db_cursor.execute("CREATE TABLE spell_school (\
            id INTEGER PRIMARY KEY, school_id INT,\
            spell_id INT)")

    elif(name == 'subtype'):
        db_cursor.execute("CREATE TABLE subtype (\
            id INTEGER PRIMARY KEY, name TINYTEXT)")

    elif(name == 'spell_subtype'):
        db_cursor.execute("CREATE TABLE spell_subtype (\
            id INTEGER PRIMARY KEY, subtype_id INT,\
            spell_id INT)")

    elif(name == 'component'):
        db_cursor.execute("CREATE TABLE component (\
            id INTEGER PRIMARY KEY, name TINYTEXT,\
            short_hand TINYTEXT)")

    elif(name == 'spell_component'):
        db_cursor.execute("CREATE TABLE spell_component (\
            id INTEGER PRIMARY KEY, component_id INT,\
            spell_id INT)")


def preload_tables(db_cursor):
    """
        Let's preload some of the tables:
    """
    #Load up all domains
    cleric_domain_file = open('data/cleric_domains.txt', 'r')
    for line in cleric_domain_file:
        db_cursor.execute("SELECT id FROM domain WHERE name = ?", (line.strip(), ))
        if not db_cursor.fetchone():
            db_cursor.execute("INSERT INTO domain VALUES (NULL, ?)",
                              (line.strip(), ))

    #Add in the normal spell components
    spell_components = {
        'V': 'Verbal',
        'S': 'Somatic',
        'M': 'Material',
        'F': 'Focus',
        'DF': 'Divine Focus',
        'XP': 'XP Cost'
    }
    for component_type in spell_components:
        db_cursor.execute("SELECT id FROM component WHERE short_hand = ?", (component_type,))
        if not db_cursor.fetchone():
            db_cursor.execute("INSERT INTO component VALUES (NULL, ?, ?)",
                              (spell_components[component_type], component_type))

    db_cursor.execute("SELECT id FROM class WHERE name = ?", ("Divine Bard",))
    if not db_cursor.fetchone():
        db_cursor.execute("INSERT INTO class VALUES (NULL, ?, 0, 0, 0)", ("Divine Bard",))
    db_cursor.execute("SELECT id FROM class WHERE name = ?", ("Divine Savant",))
    if not db_cursor.fetchone():
        db_cursor.execute("INSERT INTO class VALUES (NULL, ?, 0, 0, 0)", ("Divine Savant",))


def stitch_together_parens(level_lines):
    paran_sections = []
    for pos in range(len(level_lines)):
        if "(" in level_lines[pos] and ")" not in level_lines[pos]:
            paran_sections.append([pos])
        if "(" not in level_lines[pos] and ")" in level_lines[pos]:
            paran_sections[-1].append(pos)
    for section in reversed(paran_sections):
        level_lines[section[0]:section[1]+1] = [', '.join(level_lines[section[0]:section[1]+1])]
    return level_lines


def break_out_class_subtype(character_class):
    if "(" in character_class:
        character_class = character_class.strip().split(" (")
        classes_to_subtype = [
            "Cleric",
            "Wu Jen",
            "Shugenja",
            "Arachnomancer",
            "Spelldancer",
            "Pious Templar",
            "Maho-Tsukai",
            "Savant"
        ]
        if character_class[0] in classes_to_subtype:
            character_class[1] = character_class[1][:-2]
            if character_class[0] == "Savant":
                character_class[1] = character_class[1][:-2].split(" ")
        else:
            character_class = [" (".join(character_class)]
    else:
        character_class = [character_class]

    return character_class


def parse_spell(spell, db_cursor):
    """
        Let's parse a spell chunk
    """
    global alt_spells
    global web_abbrev
    global all_descriptors
    spell_line = spell.pop(0).strip()

    #Handle the See "this spell" for info cases
    match = re.search('See "(.+)"', spell[0])
    if match:
        alt_spells.append([spell_line.strip(), match.group(1)])
        return

    # First get the spell name and book with page number
    match = re.search('(.+) \[(.+)\]', spell_line)
    spell_name = match.group(1)
    book_info = match.group(2)
    book_info = book_info.split(", ")
    book_info = stitch_together_parens(book_info)

    # Spells can have multiple books
    for x in range(len(book_info)):
        # Books may or may not have a page number
        book_info[x] = book_info[x].strip()
        match = re.search('\(pg\s?(\d+(, \d+)*)\)', book_info[x])
        if match:
            page = match.group(1).split(', ')
            book_name = re.search('(.+) \(pg\s?\d+(, \d+)*\)', book_info[x]).group(1)
        else:
            page = None
            book_name = book_info[x]
        #Handle web abbreviations
        if book_name in web_abbrev:
            book_name = web_abbrev[book_name]
        book_info[x] = [book_name, page]

    # Now lets figure out the type and sub-type
    # Because not every spell has a type.
    schools = []
    sub_types = []
    if not re.match("\w+( \w+)*:", spell[0]):
        type_line = spell.pop(0)
        schools = type_line.split()[0].split("/")
        match = re.search('\((.+)\)', type_line)
        if match:
            sub_types.extend([sub_type.strip() for sub_type in match.group(1).split(",")])
        match = re.search('\[(.+)\]', type_line)
        if match:
            sub_types.extend([sub_type.strip() for sub_type in match.group(1).split(",")])

    #Now let's grab the classes and levels
    if spell[0].lower().startswith("level: "):
        classes = {}
        level_lines = [spell.pop(0).strip()]
        while True:
            if spell[0].startswith('    '):
                break
            if len(spell) == 0:
                break
            if re.match("\w+( \w+)*:", spell[0]):
                break
            level_lines.append(spell.pop(0).strip())
        level_lines = filter(None, " ".join(level_lines).replace("Level: ", '').split(', '))
        level_lines = stitch_together_parens(level_lines)
        # Now lets separate class from level. We may need to come back to
        # this point later.
        for class_level in level_lines:
            match = re.search('(\d+)\-(\d+)', class_level)
            if match:
                level = range(int(match.group(1)), int(match.group(2)) + 1)
                character_class = re.sub(' \d+\-\d+', '', class_level, count=1)
            else:
                level = [int(re.search('(\d+)', class_level).group(1))]
                character_class = re.sub(' \d+', '', class_level, count=1).strip()
            character_class = break_out_class_subtype(character_class)

            #There are some class specific edge cases.
            if character_class[0] == "Sorcerer/Wizard":
                character_class[0] = character_class[0].split("/")
                classes[character_class[0][0]] = [level]
                classes[character_class[0][1]] = [level]
            elif character_class[0] == "Bard":
                classes[character_class[0]] = [level]
                classes["Divine Bard"] = [level]
            elif len(character_class) == 2:
                classes[character_class[0]] = [level, character_class[1]]
            else:
                classes[character_class[0]] = [level]

    # Now need to break everything else out
    spell_info = {}
    while True:
        #You've hit the description yay!
        if spell[0].startswith('    '):
            break
        # Magically, you have no description
        if len(spell) == 0:
            break
        # Ah, sometimes descriptors can be multiline
        spell_line = [spell.pop(0).strip()]
        while True:
            if re.match('\w+( \w+)*:', spell[0]):
                break
            if spell[0].startswith('    '):
                break
            if len(spell) == 0:
                break
            spell_line.append(spell.pop(0).strip())
        spell_line = " ".join(spell_line)

        spell_descriptor = re.match("(\w+( \w+)*): ", spell_line).group(1).lower()
        spell_descriptor = re.sub(" +", "_", spell_descriptor)
        if spell_descriptor not in all_descriptors:
            all_descriptors.append(spell_descriptor)
        spell_line = re.sub("\w+( \w+)*: ", '', spell_line, count=1)
        spell_info[spell_descriptor] = spell_line

    #Now stich together the rest of the description
    spell_info['description'] = "".join(spell).strip()
    if 'components' in spell_info:
        spell_info['components'] = spell_info['components'].split(", ")

    # You should populate the spell first so you can populate other tables
    # and link tables as we go.

    # Initial spell insert:
    db_cursor.execute("SELECT id from spell WHERE name = ? LIMIT 1", (spell_name,))
    if not db_cursor.fetchone():
        db_cursor.execute("INSERT INTO spell VALUES(NULL, ?, NULL, NULL, NULL,\
                           NULL, NULL, NULL, NULL, NULL, NULL)", (spell_name,))
        db_cursor.execute("SELECT id from spell WHERE name = ? LIMIT 1", (spell_name,))
        spell_id = db_cursor.fetchone()[0]

        # Let's populate reference tables as we go:
        ## BOOK ##
        for book in book_info:
            db_cursor.execute("SELECT id FROM book WHERE name = ? LIMIT 1", (book[0],))
            book_id = db_cursor.fetchone()
            if not book_id:
                db_cursor.execute("INSERT INTO book VALUES(NULL, ?)", (book[0],))
                db_cursor.execute("SELECT id FROM book WHERE name = ? LIMIT 1", (book[0],))
                book_id = db_cursor.fetchone()
            book_id = book_id[0]
            if book[1]:
                for page in book[1]:
                    db_cursor.execute("INSERT INTO spell_book VALUES(NULL, ?, ?, ?)",
                                      (book_id, spell_id, page))
            else:
                db_cursor.execute("INSERT INTO spell_book VALUES(NULL, ?, ?, NULL)",
                                  (book_id, spell_id))

        ## School ##
        for school in schools:
            db_cursor.execute("SELECT id FROM school WHERE name = ? LIMIT 1", (school,))
            school_id = db_cursor.fetchone()
            if not db_cursor.fetchone():
                db_cursor.execute("INSERT INTO school VALUES(NULL, ?)", (school,))
                db_cursor.execute("SELECT id FROM school WHERE name = ? LIMIT 1", (school,))
                school_id = db_cursor.fetchone()
            school_id = school_id[0]
            db_cursor.execute("INSERT INTO spell_school VALUES(NULL, ?, ?)", (spell_id, school_id))

        ## Subtype ##
        for sub_type in sub_types:
            db_cursor.execute("SELECT id FROM subtype WHERE name = ? LIMIT 1", (sub_type,))
            subtype_id = db_cursor.fetchone()
            if not db_cursor.fetchone():
                db_cursor.execute("INSERT INTO subtype VALUES(NULL, ?)", (sub_type,))
                db_cursor.execute("SELECT id FROM subtype WHERE name = ? LIMIT 1", (sub_type,))
                subtype_id = db_cursor.fetchone()
            subtype_id = subtype_id[0]
            db_cursor.execute("INSERT INTO spell_subtype VALUES(NULL, ?, ?)", (spell_id, subtype_id))

        ## Classes ##
        # Remember to skip domains
        for class_name in classes:
            db_cursor.execute("SELECT id FROM class WHERE name = ? LIMIT 1", (class_name,))
            if not db_cursor.fetchone():
                db_cursor.execute("SELECT id FROM domain WHERE name = ? LIMIT 1", (class_name,))
                if not db_cursor.fetchone():
                    db_cursor.execute("INSERT INTO class VALUES(NULL, ?, 0, 0, 0)", (class_name,))

    ## Components ##

    #print "\nSpell: %s" % spell_name
    #print book_info
    #print schools
    #print sub_types
    #print classes
    #for spell_descriptor in spell_info:
    #    print "%s: %s" % (spell_descriptor, spell_info[spell_descriptor])

all_descriptors = []

tables = ['spell', 'spell_class', 'class', 'spell_domain', 'domain']
tables.extend(['book', 'school', 'spell_school', 'subtype', 'spell_subtype'])
tables.extend(['spell_book', 'component', 'spell_component'])

db_conn = sqlite3.connect('spells.db')
db_conn.text_factory = str
db_cursor = db_conn.cursor()

db_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
table_results = db_cursor.fetchall()
print table_results
for table in tables:
    if not any(table == result[0] for result in table_results):
        try:
            table_setup(table, db_cursor)
            db_conn.commit()
        except Exception, e:
            traceback.print_exc()
            db_cursor.close()
            db_conn.close()
            exit(1)

#Create a memoizie table of Web abbreviations
web_abbrevation_file = open('data/web-source-abbrev.txt', 'r')
web_abbrev = {}
for line in web_abbrevation_file:
    line = line.strip()
    line = line.split(">")
    web_abbrev[line[0]] = line[1]


preload_tables(db_cursor)


"""
    Now let's parse the spell list! :D
"""
alt_spells = []
all_spells_file = open('data/all-spells.txt', 'r')
spell = []
for line in all_spells_file:
    #End of the file
    if re.match('\-+', line):
        break

    if not line.strip():
        parse_spell(spell, db_cursor)
        del spell[:]
        #break
        continue
    spell.append(line)

#print "Alt spells: %s" % alt_spells

db_cursor.execute("SELECT name FROM class")
books = list(db_cursor.fetchall())

for book in range(len(books)):
    books[book] = books[book][0]
for book in sorted(books):
    print book

    db_cursor.close()
db_conn.close()

"""
Add Divine Bard as a separate class and to any
spell that has Bard as a class
"""

"""
Populate Classes, Book, Type, and Subtype tables as you run trough the txt file
Domain should be generated off the other pdf that Noah gave me.
"""
