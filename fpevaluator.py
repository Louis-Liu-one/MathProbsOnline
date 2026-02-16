
from textwrap import indent  # 调试用

import re
import types
import functools
import sympy as sp
from pyparsing import Literal, Suppress, Word, Regex
from pyparsing import Forward, Opt, ZeroOrMore
from pyparsing import identchars, identbodychars


__all__ = ['fpeval']

indent = functools.partial(indent, prefix='    ')  # 调试用

_function_type = type | types.FunctionType | sp.FunctionClass

def _update_funceval(ns, funceval):
    ns.update({'eval': funceval})


def _as_fpelement(obj):
    return obj if isinstance(obj, FPElement) else FPExpression(obj)


def _ident2symbol(ident):
    if isinstance(ident, _function_type):
        return sp.Symbol(ident.__name__)
    return sp.Symbol(str(ident))


def _as_negative(expr):
    return sp.Mul(expr, sp.S.NegativeOne)


def _as_reciprocal(expr):
    return sp.Pow(expr, sp.S.NegativeOne)


def _continuous_pow(*exprs):
    result = exprs[-1]
    for i in range(len(exprs) - 2, -1, -1):
        result = sp.Pow(exprs[i], result)
    return result


class FPElement:

    def __str__(self):
        return repr(self)

    def do(self, context=None):
        '''执行语句。'''
        pass


class FPExpression(FPElement):
    '''表达式。'''

    def __init__(self, spexpr):
        self.expr = spexpr
        if isinstance(spexpr, FPExpression):
            self.expr = spexpr.expr
        self.expr = sp.simplify(self.expr)

    def __repr__(self):
        return f'FPExpression(\n{indent(sp.pretty(self.expr))}\n)'

    def do(self, context=None):
        return self.expr if context is None else self.expr.subs(context)


class ReturnStatement(FPElement):
    '''返回语句。'''

    def __init__(self, expr):
        self.expr = FPExpression(expr)

    def __repr__(self):
        return f'Return({self.expr})'

    def do(self, context=None):
        return self.expr.do(context)


class Assignment(FPElement):
    '''赋值语句。'''

    def __init__(self, varsymbol, varexpr):
        self.varsymbol, self.varexpr = varsymbol, FPExpression(varexpr)

    def __repr__(self):
        return f'Assignment({self.varsymbol} = {self.varexpr})'

    def do(self, context):
        result = self.varexpr.do(context)
        context[self.varsymbol] = result
        return result


class FuncDefine(FPElement):
    '''函数定义。'''

    def __init__(self, funcident, funcargs, funcbody):
        self.funcident = sp.Function(str(funcident))          # 函数名称
        self.funcargs = [str(arg) for arg in funcargs]        # 参数列表
        self.funcbody = funcbody if isinstance(
            funcbody, FPElement) else FPExpression(funcbody)  # 函数主体

        @classmethod
        def _func_eval(cls, *args):
            args = list(args)
            kwargs = args.pop() if args and isinstance(
                args[-1], dict | sp.Dict) else {}
            return self.funcbody.do({
                **dict(zip(self.funcargs, args)), **kwargs})

        self.function = types.new_class(
            str(funcident), (sp.Function,), {},
            functools.partial(_update_funceval, funceval=_func_eval))

    def __repr__(self):
        return f'FuncDefine({self.funcident}' \
            f'({', '.join(self.funcargs)}) =\n' \
            f'{indent(str(self.funcbody))}\n)'

    def do(self, context):
        context[self.funcident] = self.function


class Judgement(FPElement):
    '''判断语句。'''

    def __init__(self, condition, ifbody, elsebody):
        self.condition = condition
        self.ifbody, self.elsebody = ifbody, elsebody

    def __repr__(self):
        return f'Judgement(if {self.condition}\n' \
            f'{indent(str(self.ifbody))}\n' \
            f'else\n{indent(str(self.elsebody))}\n)'

    def do(self, context=None):
        if context is None:
            context = {}
        if self.condition.do(context):
            return self.ifbody.do(context)
        elif self.elsebody is not None:
            return self.elsebody.do(context)


class WhileLoop(FPElement):
    '''while循环语句。'''

    def __init__(self, condition, body):
        self.condition, self.body = condition, body

    def __repr__(self):
        return f'WhileLoop(while {self.condition}\n' \
            f'{indent(str(self.body))}\n)'

    def do(self, context=None):
        if context is None:
            context = {}
        while self.condition.do(context):
            self.body.do(context)


class Statements(FPElement):
    '''多条语句组合。'''

    def __init__(self, statements=None):
        self.statements = [] if statements is None else statements

    def __repr__(self):
        return f'Statements(\n' \
            + ',\n'.join([indent(str(statement))
                for statement in self.statements]) + '\n)'

    def do(self, context=None):
        if context is None:
            context = {}
        result = None
        for statement in self.statements:
            result = statement.do(context)
            if isinstance(statement, ReturnStatement):
                return result
        return result


class StatementsBlock(FPElement):
    '''语句块。'''

    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        return f'StatementsBlock(\n{indent(str(self.statements))}\n)'

    def do(self, context=None):
        return self.statements.do(context)


def _as_spident(tokens):
    identifier = tokens[0]
    if hasattr(sp, identifier):
        constant = getattr(sp, identifier)
        return sp.Symbol(identifier) if isinstance(
            constant, _function_type | sp.Lambda) else constant
    return sp.Symbol(identifier)


def _as_sprational(tokens):
    return sp.Rational(tokens[0])


def _as_spint(tokens):
    return sp.Integer(tokens[0])


def _process_binops(tokens, operation, specprocs=None):
    operands = [tokens[0]]
    for i in range(1, len(tokens), 2):
        operator, operand = tokens[i], tokens[i + 1]
        operands.append(
            specprocs[operator](operand)
            if specprocs and operator in specprocs else operand)
    return operation(*operands) if len(operands) > 1 else operands[0]


def _process_unops(tokens, specprocs=None):
    *tokens, result = tokens
    for operator in tokens:
        if isinstance(operator, Literal | str):
            result = specprocs[operator](result) \
                if specprocs and operator in specprocs else result
    return result


_as_disjunction = functools.partial(_process_binops, operation=sp.Or)
_as_conjunction = functools.partial(_process_binops, operation=sp.And)
_as_inversion = functools.partial(_process_unops, specprocs={'not': sp.Not})
_as_sum = functools.partial(
    _process_binops, operation=sp.Add, specprocs={'-': _as_negative})
_as_term = functools.partial(
    _process_binops, operation=sp.Mul, specprocs={'/': _as_reciprocal})
_as_factor = functools.partial(_process_unops, specprocs={'-': _as_negative})
_as_power = functools.partial(_process_binops, operation=_continuous_pow)
_statements = functools.partial(Statements)


def _as_comparison(tokens):
    prev_operand, *tokens = tokens
    result = []
    for i in range(0, len(tokens), 2):
        operator, operand = tokens[i], tokens[i + 1]
        result.append(COMPDICT[operator](prev_operand, operand))
        prev_operand = operand
    return sp.And(*result) if result else prev_operand


def _as_kwargs(tokens):
    return {
        _ident2symbol(tokens[i]): tokens[i + 2]
        for i in range(0, len(tokens), 3)}


def _as_parenexpr(tokens):
    identifier, *args = tokens
    kwargs = args.pop() if args and isinstance(args[-1], dict) else {}
    if isinstance(identifier, _function_type):
        return identifier(*args, **kwargs)
    elif hasattr(sp, str(identifier)):
        return getattr(sp, str(identifier))(*args, **kwargs)
    # 自定义函数关键字参数直接以字典形式传递
    function = sp.Function(str(identifier))
    return function(*args, kwargs) if kwargs else function(*args)


def _return_stmt(tokens):
    return ReturnStatement(tokens[1])


def _assignment_stmt(tokens):
    varsymbol, _, varexpr = tokens
    return Assignment(varsymbol, varexpr)


def _funcdefine_stmt(tokens):
    funcident, *funcargs, _, funcbody = tokens
    return FuncDefine(funcident, funcargs, funcbody)


def _judgement(tokens):
    _, condition, ifbody, *elsepart = tokens
    _, elsebody = elsepart if elsepart else (None, None)
    return Judgement(_as_fpelement(condition), ifbody, elsebody)


def _whileloop(tokens):
    _, condition, body = tokens
    return WhileLoop(_as_fpelement(condition), body)


def _as_statement(tokens):
    return _as_fpelement(tokens[0])


def _as_stmtsblock(tokens):
    return StatementsBlock(tokens[0])


ASSIGN, PLUS, MINUS, TIMES, DIVIDE, POWER = map(Literal, '=+-*/^')
COMP_LT, COMP_LE, COMP_EQ, COMP_NE, COMP_GE, COMP_GT = map(
    Literal, ['<', '<=', '==', '!=', '>=', '>'])
COMPARISON = COMP_LE | COMP_GE | COMP_NE | COMP_EQ | COMP_LT | COMP_GT
COMPDICT = {
    '<': sp.Lt, '<=': sp.Le, '==': sp.Eq,
    '!=': sp.Ne, '>=': sp.Ge, '>': sp.Gt}
LPAREN, RPAREN, LBRACE, RBRACE, SEMICOL, COMMA = map(Suppress, '(){};,')
KW_NOT, KW_AND, KW_OR, KW_RETURN, KW_IF, KW_ELSE, KW_WHILE = map(
    Literal, ['not', 'and', 'or', 'return', 'if', 'else', 'while'])
IDENTIFIER = Word(identchars, identbodychars).set_parse_action(_as_spident)
FLOAT_REGEX = re.compile(
    r'((([1-9]\d*|0)\.\d*)|(([1-9]\d*|0)?\.\d+))([eE][+-]?\d+)?')
INT_REGEX = re.compile(r'[1-9]\d*|0')
FLOAT_ATOM = Regex(FLOAT_REGEX).set_parse_action(_as_sprational)
INT_ATOM = Regex(INT_REGEX).set_parse_action(_as_spint)

'''
BNF:
<atom>        ::= INT_ATOM | FLOAT_ATOM | IDENTIFIER
<kwargs>      ::= IDENTIFIER "=" <expr> { "," IDENTIFIER "=" <expr> }
<parenexpr>   ::= <expr> | IDENTIFIER
                  "(" { <expr> "," } [ [ <expr> "," ] <kwargs>
                  | <expr> ] [ "," ] ")" | <atom>
<power>       ::= <parenexpr> { "^" <parenexpr> }
<factor>      ::= { "+" | "-" } <power>
<term>        ::= <factor> { "*" <factor> | "/" <factor> }
<sum>         ::= <term> { "+" <term> | "-" <term> }
<comparison>  ::= <sum> { ( "<" | "<=" | "==" | ">=" | ">" ) <sum> }
<inversion>   ::= { "not" } <comparison>
<conjunction> ::= <inversion> { "and" <inversion> }
<disjunction> ::= <conjunction> { "or" <conjunction> }
<expr>        ::= <disjunction>
<assignment>  ::= IDENTIFIER "=" <expr>
<funcdefine>  ::= IDENTIFIER LPAREN [ IDENTIFIER { "," IDENTIFIER } [ "," ] ]
                  RPAREN "=" ( <expr> | <stmtsblock> )
<return>      ::= "return" <expr>
<judgement>   ::= "if" <parenexpr> ( <statement> | <stmtsblock> )
                  [ "else" ( <statement> | <stmtsblock> ) ]
<whileloop>   ::= "while" <parenexpr> ( <statement> | <stmtsblock> )
<statement>   ::= <assignment> | <funcdefine> | <return>
                  | <judgement> | <whileloop> | <stmtsblock> | <expr>
<statements>  ::= <statement> { ";" <statement> } [ ";" ]
<stmtsblock>  ::= "{" <statements> "}"
'''

RULE_atom = FLOAT_ATOM | INT_ATOM | IDENTIFIER
RULE_expr = Forward()
RULE_statement = Forward()
RULE_stmtsblock = Forward()

RULE_kwargs = (IDENTIFIER + ASSIGN + RULE_expr + ZeroOrMore(
    COMMA + IDENTIFIER + ASSIGN + RULE_expr)).set_parse_action(_as_kwargs)
RULE_parenexpr = (LPAREN + RULE_expr + RPAREN) | (
    IDENTIFIER + LPAREN + ZeroOrMore(RULE_expr + COMMA)
    + Opt((Opt(RULE_expr + COMMA) + RULE_kwargs) | RULE_expr)
    + Opt(COMMA) + RPAREN).set_parse_action(_as_parenexpr) | RULE_atom

RULE_power = (RULE_parenexpr + ZeroOrMore(
    POWER + RULE_parenexpr)).set_parse_action(_as_power)
RULE_factor = (
    ZeroOrMore(PLUS | MINUS) + RULE_power).set_parse_action(_as_factor)
RULE_term = (RULE_factor + ZeroOrMore(
    (TIMES | DIVIDE) + RULE_factor)).set_parse_action(_as_term)
RULE_sum = (RULE_term + ZeroOrMore(
    (PLUS | MINUS) + RULE_term)).set_parse_action(_as_sum)
RULE_comparison = (RULE_sum + ZeroOrMore(
    COMPARISON + RULE_sum)).set_parse_action(_as_comparison)
RULE_inversion = (ZeroOrMore(
    KW_NOT) + RULE_comparison).set_parse_action(_as_inversion)
RULE_conjunction = (RULE_inversion + ZeroOrMore(
    KW_AND + RULE_inversion)).set_parse_action(_as_conjunction)
RULE_disjunction = (RULE_conjunction + ZeroOrMore(
    KW_OR + RULE_conjunction)).set_parse_action(_as_disjunction)
RULE_expr << RULE_disjunction

RULE_assignment = (
    IDENTIFIER + ASSIGN + RULE_expr).set_parse_action(_assignment_stmt)
RULE_funcdefine = (
    IDENTIFIER + LPAREN + Opt(
        IDENTIFIER + ZeroOrMore(COMMA + IDENTIFIER) + Opt(COMMA))
    + RPAREN + ASSIGN + (RULE_expr | RULE_stmtsblock)
    ).set_parse_action(_funcdefine_stmt)
RULE_return = (KW_RETURN + RULE_expr).set_parse_action(_return_stmt)
RULE_judgement = (
    KW_IF + RULE_parenexpr + (RULE_statement | RULE_stmtsblock)
    + Opt(KW_ELSE + (RULE_statement | RULE_stmtsblock))
    ).set_parse_action(_judgement)
RULE_whileloop = (
    KW_WHILE + RULE_parenexpr
    + (RULE_statement | RULE_stmtsblock)).set_parse_action(_whileloop)
RULE_statement << (
    RULE_assignment | RULE_funcdefine | RULE_return
    | RULE_judgement | RULE_whileloop | RULE_stmtsblock
    | RULE_expr).set_parse_action(_as_statement)

RULE_statements = (
    RULE_statement + ZeroOrMore(SEMICOL + RULE_statement)
    + Opt(SEMICOL)).set_parse_action(_statements)
RULE_stmtsblock << (
    LBRACE + RULE_statements + RBRACE).set_parse_action(_as_stmtsblock)


def fpeval(string):
    '''计算语句的返回值。'''
    return RULE_statements.parse_string(string)[0]
