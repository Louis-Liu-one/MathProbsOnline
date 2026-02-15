
import operator
import re
import sympy as sp
from pyparsing import Literal, Suppress, Word, Regex
from pyparsing import Forward, Group, Opt, ZeroOrMore
from pyparsing import identchars, identbodychars


__all__ = ['fpeval']


class FPElement:

    def __str__(self):
        return repr(self)

    def do(self, context=None):
        pass


class FPExpression(FPElement):

    def __init__(self, spexpr):
        self.expr = spexpr
        if isinstance(spexpr, FPExpression):
            self.expr = spexpr.expr
        self.expr = sp.simplify(self.expr)

    def __repr__(self):
        return f'FPExpression({self.expr})'

    def do(self, context=None):
        return self.expr if context is None else self.expr.subs(context)


class ReturnStatement(FPElement):

    def __init__(self, expr):
        self.expr = FPExpression(expr)

    def __repr__(self):
        return f'Return({self.expr})'

    def do(self, context=None):
        return self.expr.do(context)


class Assignment(FPElement):

    def __init__(self, varsymbol, varexpr):
        self.varsymbol, self.varexpr = varsymbol, FPExpression(varexpr)

    def __repr__(self):
        return f'Assignment({self.varsymbol} = {self.varexpr})'

    def do(self, context):
        context[self.varsymbol] = self.varexpr.do(context)


class Statements(FPElement):

    def __init__(self, statements=None):
        self.statements = [] if statements is None else statements

    def __repr__(self):
        return f'Statements({self.statements})'

    def add_statement(self, statement):
        if statement is not None:
            self.statements.append(statement)

    def do(self, context=None):
        if context is None:
            context = {}
        if len(self.statements) == 1 and isinstance(
                self.statements[0], FPExpression):
            return self.statements[0].do(context)
        for statement in self.statements:
            result = statement.do(context)
            if isinstance(statement, ReturnStatement):
                return result


def _as_spident(tokens):
    return sp.Symbol(tokens[0])


def _as_sprational(tokens):
    return sp.Rational(tokens[0])


def _as_spint(tokens):
    return sp.Integer(tokens[0])


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
    return _calc_tokens(tokens[0], PLUS, operator.add, operator.sub, 0)


def _as_term(tokens):
    return _calc_tokens(tokens[0], TIMES, operator.mul, operator.truediv)


def _as_factor(tokens):
    symbol = True
    for token in tokens[0]:
        if isinstance(token, Literal | str):
            symbol ^= token == MINUS
    return tokens[0][-1] if symbol else -tokens[0][-1]


def _as_power(tokens):
    return _calc_tokens(tokens[0], POWER, operator.pow, None, rev=True)


def _as_parenexpr(tokens):
    identifier = str(tokens[0][0])
    args = tokens[0][1:]
    if hasattr(sp, identifier):
        return getattr(sp, identifier)(*args)
    return sp.Function(identifier)(*args)


def _return_stmt(tokens):
    return ReturnStatement(tokens[0][1])


def _assignment_stmt(tokens):
    varsymbol, varexpr = tokens[0][0], tokens[0][2]
    return Assignment(varsymbol, varexpr)


def _statements(tokens):
    statements = Statements()
    for statement in tokens[0]:
        statements.add_statement(
            statement if isinstance(statement, FPElement)
            else FPExpression(statement))
    return statements


ASSIGN, PLUS, MINUS, TIMES, DIVIDE, POWER = map(Literal, '=+-*/^')
LPAREN, RPAREN, SEMICOL, COMMA = map(Suppress, '();,')
KW_RETURN = Literal('return')
IDENTIFIER = Word(identchars, identbodychars).set_parse_action(_as_spident)
FLOAT_REGEX = re.compile(
    r'((([1-9]\d*|0)\.\d*)|(([1-9]\d*|0)?\.\d+))([eE][+-]?\d+)?')
INT_REGEX = re.compile(r'[1-9]\d*|0')
FLOAT_ATOM = Regex(FLOAT_REGEX).set_parse_action(_as_sprational)
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
<return>     ::= "return" <expr>
<statement>  ::= <assignment> | <return> | <expr>
<statements> ::= <statement> { ";" <statement> } [ ";" ]
'''

RULE_atom = FLOAT_ATOM | INT_ATOM | IDENTIFIER
RULE_expr = Forward()
RULE_parenexpr = (LPAREN + RULE_expr + RPAREN) | Group(
    IDENTIFIER + LPAREN + RULE_expr + ZeroOrMore(COMMA + RULE_expr)
    + RPAREN).set_parse_action(_as_parenexpr) | RULE_atom
RULE_power = Group(RULE_parenexpr + ZeroOrMore(
    POWER + RULE_parenexpr)).set_parse_action(_as_power)
RULE_factor = Group(
    ZeroOrMore(PLUS | MINUS) + RULE_power).set_parse_action(_as_factor)
RULE_term = Group(RULE_factor + ZeroOrMore(
    (TIMES | DIVIDE) + RULE_factor)).set_parse_action(_as_term)
RULE_expr << Group(RULE_term + ZeroOrMore(
    (PLUS | MINUS) + RULE_term)).set_parse_action(_as_sum)
RULE_assignment = Group(
    IDENTIFIER + ASSIGN + RULE_expr).set_parse_action(_assignment_stmt)
RULE_return = Group(KW_RETURN + RULE_expr).set_parse_action(_return_stmt)
RULE_statement = RULE_assignment | RULE_return | RULE_expr
RULE_statements = Group(
    RULE_statement + ZeroOrMore(SEMICOL + RULE_statement)
    + Opt(SEMICOL)).set_parse_action(_statements)


def fpeval(string):
    return RULE_statements.parse_string(string)[0]
