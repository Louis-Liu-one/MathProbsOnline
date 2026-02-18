
import enum
from func_timeout import func_timeout, FunctionTimedOut
from fpevaluator import latex, fpparse, fpeval, ParseException

__all__ = [
    'TPStatus', 'check_answer', 'check_answers',
    'testpoints_passedlist', 'latex']


class TPStatus(enum.Enum):

    CORRECT = 1
    INCORRECT = 2
    PARSEERR = 3
    EVALERR = 4
    TIMEOUT = 5
    ANSERR = 6


def fpparse_with_timeout(answer):
    return func_timeout(.1, fpparse, args=(answer,))


def fpeval_with_timeout(parsed_answer, context=None):
    return func_timeout(.2, fpeval, args=(parsed_answer, context))


def check_answer(answer, userans_parsed, context=None):
    try:
        answer_parsed = fpparse_with_timeout(answer)
        answer_eval = fpeval_with_timeout(answer_parsed, context)
    except FunctionTimedOut:
        return TPStatus.TIMEOUT
    except Exception:
        return TPStatus.ANSERR
    try:
        userans_eval = fpeval_with_timeout(userans_parsed, context)
        return TPStatus.CORRECT if answer_eval.equals(
            userans_eval) else TPStatus.INCORRECT
    except FunctionTimedOut:
        return TPStatus.TIMEOUT
    except ParseException:
        return TPStatus.PARSEERR
    except Exception:
        return TPStatus.EVALERR


def check_answers(answers, userans):
    try:
        userans_parsed = fpparse_with_timeout(userans)
        return fpeval_with_timeout(userans_parsed), [check_answer(
            answer, userans_parsed, context) for context, answer in answers]
    except FunctionTimedOut:
        return None, [TPStatus.TIMEOUT] * len(answers)
    except ParseException:
        return None, [TPStatus.PARSEERR] * len(answers)
    except Exception:
        return None, [TPStatus.EVALERR] * len(answers)


def testpoints_passedlist(testpoints):
    return [testpoint == TPStatus.CORRECT for testpoint in testpoints]
