"""Everyday English for reading tests, written for this project (not a famous text, so a language model cannot
recite it from memory). Letters, digits and spaces only: the fonts have no punctuation yet."""

PROSE = """
Thank you for your order We have received your payment and your package will ship within two business days
You can track the delivery on our website using the reference number printed on your receipt
If anything arrives damaged please keep the box and call us so we can arrange a replacement
The meeting has been moved to Thursday afternoon because the projector in the large room is being repaired
Please bring your laptop and the quarterly figures and remember that lunch will be provided for everyone
Our office will be closed on Monday for the holiday and the help desk will reopen on Tuesday morning
The kitchen on the third floor needs a new kettle so if you notice the old one leaking do not use it
Parking in the north lot is limited this week while the painters finish the lines near the main gate
Residents are reminded that recycling is collected every other Wednesday and the bins must be at the curb by seven
Fresh bread is baked every morning and the shop opens at half past six except on Sundays when it opens at eight
The library has extended its hours during exam season and quiet study rooms can be booked a week in advance
Children under twelve must be accompanied by an adult in the swimming pool and running is not allowed on the deck
Water the tomatoes in the evening when the soil is cool and pick the fruit as soon as it turns a deep red
To reset the router hold the small button on the back for ten seconds until the lights begin to flash
The battery should last about nine hours of normal use but bright screens and video will drain it faster
Store the medicine in a cool dry place out of reach of children and do not exceed the stated dose
Mix the flour sugar and butter in a large bowl then add the eggs one at a time and stir gently
Bake the cake for forty minutes or until a knife pushed into the middle comes out clean
Allow the soup to simmer for an hour and season it with salt pepper and a little fresh thyme
The train to the airport leaves from platform four every twenty minutes between six in the morning and midnight
Passengers with large luggage should use the front carriage where there is extra space near the doors
The museum displays old maps of the city along with letters written by the families who first settled here
Visitors often stop at the bridge to watch the boats pass below and to take pictures of the hills beyond
A quiet walk along the river in the early morning is the best way to see the herons and the kingfishers
The committee agreed to review the budget again next month after the new figures have been checked
Several members asked whether the playground could be repaired before the summer holidays begin
The weather tomorrow will be mostly cloudy with light rain in the afternoon and a gentle breeze from the west
Temperatures will fall overnight and drivers should watch for ice on bridges and quiet country roads
Our customer service team is available every weekday and most questions can be answered in a few minutes
Please update your password regularly and never share it with anyone who calls claiming to be from the bank
The invoice lists each item with its quantity and price and the total includes delivery and tax
Keep a copy of this statement for your records and contact us within thirty days if you find an error
The new software update fixes several problems with printing and makes the program start more quickly
Save your work often and close other programs before installing the update to avoid losing anything
Jack quickly moved the heavy boxes of fizzy drinks into the van before the rain started again
The quiet fox jumped over the lazy dog while seven brave zebras waited by the frozen lake
Joyful children played in the park and bright kites flew high above the green fields all day
Six big jugs of milk were placed in the fridge next to a box of eggs and a jar of jam
"""

CODES = """
Order 40318 shipped on 12 May via courier 7G2K
Invoice INV 2024 0917 total 1385 dollars and 40 cents
Flight BA 2491 departs gate 17 at 0645
Room 3B on level 2 next to lift 1
Account ending 5521 sort code 40 11 62
Serial number SN8X42LQ0 model 7700Z
Postcode SW1A 2AA or ZIP 90210
Booking reference Q7HX9P for 2 adults and 1 child
Part 0O1Il 5S8B 2Z6G kit 4A
Version 3 build 1405 released 2019
"""


def prose_lines(width: int = 28) -> list[str]:
    import textwrap
    return textwrap.wrap(" ".join(PROSE.split()), width)


def code_lines() -> list[str]:
    return [l.strip() for l in CODES.strip().splitlines()]


def shuffled_lines(width: int = 28, seed: int = 7) -> list[str]:
    """The same words in random order: real words, but no sentence for the reader to predict from."""
    import random
    import textwrap
    words = " ".join(PROSE.split()).split()
    random.Random(seed).shuffle(words)
    return textwrap.wrap(" ".join(words), width)
