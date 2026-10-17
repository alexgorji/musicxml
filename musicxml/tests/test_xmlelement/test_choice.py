from unittest import TestCase

from musicxml.xmlelement.xmlelement import *


class TestChoice(TestCase):
    def test_xml_element_with_choice(self):
        xml_encoding = XMLEncoding()
        xml_encoding.add_child(XMLEncoder('bla'))
        xml_encoding.add_child(XMLEncoder('blue'))

        assert len(xml_encoding.get_children()) == 2

    def test_note_choice_replacement_with_cue_or_grace(self):
        for child_type in (XMLCue, XMLGrace):
            with self.subTest(child_type=child_type):
                note = XMLNote()
                pitch = note.add_child(XMLPitch())
                pitch.add_child(XMLStep('C'))
                pitch.add_child(XMLOctave(4))
                note.add_child(XMLDuration(1))
                if child_type is XMLGrace:
                    note.xml_duration = None
                child = note.add_child(child_type())

                self.assertIs(note.xml_pitch, pitch)
                self.assertIn(child, note.get_children())
                self.assertIn(f'<{child.name}', note.to_string())
                container = note._child_container_tree
                for node in container.traverse():
                    for descendant in node.get_children():
                        self.assertIs(descendant.get_parent(), node)
