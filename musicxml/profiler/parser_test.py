import cProfile
import datetime
from contextlib import redirect_stdout
from pathlib import Path

from musicxml.parser.parser import parse_musicxml


def p():
    start_reading = datetime.datetime.now()
    print("start reading score")
    score = parse_musicxml(Path(__file__).parent / 'parser_test.xml')
    start_writing = datetime.datetime.now()
    print(f"start writing score :{start_writing - start_reading}")
    score.write(Path(__file__).parent / 'parser_test_create.xml')
    end = datetime.datetime.now()
    print(f"end writing score :{end - start_reading}")


# with open(Path(__file__).with_suffix('.txt'), '+w') as f:
#     with redirect_stdout(f):
#         cProfile.run('p()', sort="tottime")
