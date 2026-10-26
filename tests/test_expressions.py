from unittest import TestCase

from koma.expressions import arithmetic_value, MAX_EXPRESSION_LENGTH


class ArithmeticTests(TestCase):
    def test_precedence_parentheses_decimal_and_unary_operators(self):
        for text, expected in (('24*2', 48), ('48/2', 24), ('(24+12)*2', 72),
                ('2+3*4', 14), ('1,5 / 2', .75), (' -2 + +5 ', 3), ('1e-2*100', 1)):
            with self.subTest(text=text):
                self.assertEqual(arithmetic_value(text), expected)

    def test_invalid_unsafe_or_excessive_input_is_rejected(self):
        for text in ('', '24*', '1/0', '1e309', '1e308*10', 'True', 'None',
                'abs(-2)', '__import__("os")', '(1).__class__', '[1][0]', '2**100',
                '1//2', '1%2', 'x+1', '1+' * 40 + '1', '1' * (MAX_EXPRESSION_LENGTH + 1)):
            with self.subTest(text=text), self.assertRaises(ValueError):
                arithmetic_value(text)
