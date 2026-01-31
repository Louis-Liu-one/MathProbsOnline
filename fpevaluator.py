
import operator
import re
import sympy
from pyparsing import Literal, Suppress, Word, Regex
from pyparsing import Forward, Group, ZeroOrMore
from pyparsing import identchars, identbodychars


__all__ = ['fpeval']


def _as_spsymbol(tokens):
    return sympy.Symbol(tokens[0])


def _as_spfloat(tokens):
    return sympy.Float(tokens[0])


def _as_spint(tokens):
    return sympy.Integer(tokens[0])


def _calc_tokens(tokens, spectoken, func1, func2, start=1, rev=False):
    res, flag = start, True
    for token in reversed(tokens) if rev else tokens:
        if isinstance(token, Literal | str):
            flag = token == spectoken
        else:
            res = (func1 if flag else func2)(
                *((token, res) if rev else (res, token)))
    return res


def _as_sum(tokens):
    return _calc_tokens(tokens[0], '+', operator.add, operator.sub, 0)


def _as_term(tokens):
    return _calc_tokens(tokens[0], '*', operator.mul, operator.truediv)


def _as_factor(tokens):
    symbol = True
    for token in tokens[0]:
        if isinstance(token, Literal | str):
            symbol ^= token == '-'
    return tokens[0][-1] if symbol else -tokens[0][-1]


def _as_power(tokens):
    return _calc_tokens(tokens[0], '^', operator.pow, None, rev=True)


def _as_parenexpr(tokens):
    return getattr(sympy, str(tokens[0][0]))(tokens[0][1])


ASSIGN, PLUS, MINUS, TIMES, DIVIDE, POWER = map(Literal, '=+-*/^')
LPAREN, RPAREN = map(Suppress, '()')
IDENTIFIER = Word(identchars, identbodychars).set_parse_action(_as_spsymbol)
FLOAT_REGEX = re.compile(
    r'((([1-9]\d*|0)\.\d*)|(([1-9]\d*|0)?\.\d+))([eE][+-]?\d+)?')
INT_REGEX = re.compile(r'[1-9]\d*|0')
FLOAT_ATOM = Regex(FLOAT_REGEX).set_parse_action(_as_spfloat)
INT_ATOM = Regex(INT_REGEX).set_parse_action(_as_spint)

'''
BNF:
<atom>       ::= INT_ATOM | FLOAT_ATOM | IDENTIFIER
<parenexpr>  ::= [ IDENTIFIER ] "(" <expr> ")" | <atom>
<power>      ::= <parenexpr> { "^" <parenexpr> }
<factor>     ::= { "+" | "-" } <power>
<term>       ::= <factor> { "*" <factor> | "/" <factor> }
<expr>       ::= <term> { "+" <term> | "-" <term> }
<assignment> ::= IDENTIFIER "=" <expr>
<statement>  ::= <assignment> | <expr>
'''

RULE_atom = FLOAT_ATOM | INT_ATOM | IDENTIFIER
RULE_expr = Forward()
RULE_parenexpr = (LPAREN + RULE_expr + RPAREN) | Group(
    IDENTIFIER + LPAREN + RULE_expr + RPAREN).set_parse_action(
    _as_parenexpr) | RULE_atom
RULE_power = Group(RULE_parenexpr + ZeroOrMore(
    POWER + RULE_parenexpr)).set_parse_action(_as_power)
RULE_factor = Group(
    ZeroOrMore(PLUS | MINUS) + RULE_power).set_parse_action(_as_factor)
RULE_term = Group(RULE_factor + ZeroOrMore(
    (TIMES | DIVIDE) + RULE_factor)).set_parse_action(_as_term)
RULE_expr << Group(RULE_term + ZeroOrMore(
    (PLUS | MINUS) + RULE_term)).set_parse_action(_as_sum)
RULE_assignment = Group(IDENTIFIER + ASSIGN + RULE_expr)
RULE_statement = RULE_assignment | RULE_expr


def fpeval(expr):
    return RULE_statement.parse_string(expr)[0]
