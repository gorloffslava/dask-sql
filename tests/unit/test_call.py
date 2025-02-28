import datetime
import operator
from unittest.mock import MagicMock

import dask.dataframe as dd
import numpy as np
import pandas as pd

import dask_sql.physical.rex.core.call as call
from tests.utils import assert_eq

df1 = dd.from_pandas(pd.DataFrame({"a": [1, 2, 3]}), npartitions=1)
df2 = dd.from_pandas(pd.DataFrame({"a": [3, 2, 1]}), npartitions=1)
df3 = dd.from_pandas(
    pd.DataFrame({"a": [True, pd.NA, False]}, dtype="boolean"), npartitions=1
)
ops_mapping = call.RexCallPlugin.OPERATION_MAPPING


def test_operation():
    operator = MagicMock()
    operator.return_value = "test"

    op = call.Operation(operator)

    assert op("input") == "test"
    operator.assert_called_once_with("input")


def test_reduce():
    op = call.ReduceOperation(operator.add)

    assert op(1, 2, 3) == 6


def test_case():
    op = call.CaseOperation()

    assert_eq(op(df1.a > 2, df1.a, df2.a), pd.Series([3, 2, 3]), check_names=False)

    assert_eq(op(df1.a > 2, 99, df2.a), pd.Series([3, 2, 99]), check_names=False)

    assert_eq(op(df1.a > 2, 99, -1), pd.Series([-1, -1, 99]), check_names=False)

    assert_eq(op(df1.a > 2, df1.a, -1), pd.Series([-1, -1, 3]), check_names=False)

    assert op(True, 1, 2) == 1
    assert op(False, 1, 2) == 2


def test_is_true():
    op = call.IsTrueOperation()

    assert_eq(op(df1.a > 2), pd.Series([False, False, True]), check_names=False)
    assert_eq(
        op(df3.a),
        pd.Series([True, False, False], dtype="boolean"),
        check_names=False,
    )

    assert op(1)
    assert not op(0)
    assert not op(None)
    assert not op(np.NaN)
    assert not op(pd.NA)


def test_is_false():
    op = call.IsFalseOperation()

    assert_eq(op(df1.a > 2), pd.Series([True, True, False]), check_names=False)
    assert_eq(
        op(df3.a),
        pd.Series([False, False, True], dtype="boolean"),
        check_names=False,
    )

    assert not op(1)
    assert op(0)
    assert not op(None)
    assert not op(np.NaN)
    assert not op(pd.NA)


def test_like():
    op = call.LikeOperation()

    assert op("a string", r"%a%")
    assert op("another string", r"a%")
    assert not op("another string", r"s%")

    op = call.SimilarOperation()
    assert op("normal", r"n[a-z]rm_l")
    assert not op("not normal", r"n[a-z]rm_l")


def test_not():
    op = call.NotOperation()

    assert op(False)
    assert not op(True)

    assert not op(3)


def test_nan():
    op = call.IsNullOperation()

    assert op(None)
    assert op(np.NaN)
    assert op(pd.NA)
    assert_eq(op(pd.Series(["a", None, "c"])), pd.Series([False, True, False]))
    assert_eq(
        op(pd.Series([3, 2, np.NaN, pd.NA])), pd.Series([False, False, True, True])
    )


def test_simple_ops():
    assert_eq(
        ops_mapping["and"](df1.a >= 2, df2.a >= 2),
        pd.Series([False, True, False]),
        check_names=False,
    )

    assert_eq(
        ops_mapping["or"](df1.a >= 2, df2.a >= 2),
        pd.Series([True, True, True]),
        check_names=False,
    )

    assert_eq(
        ops_mapping[">="](df1.a, df2.a),
        pd.Series([False, True, True]),
        check_names=False,
    )

    assert_eq(
        ops_mapping["+"](df1.a, df2.a, df1.a),
        pd.Series([5, 6, 7]),
        check_names=False,
    )


def test_math_operations():
    assert_eq(
        ops_mapping["abs"](-df1.a),
        pd.Series([1, 2, 3]),
        check_names=False,
    )
    assert_eq(
        ops_mapping["round"](df1.a),
        pd.Series([1, 2, 3]),
        check_names=False,
    )
    assert_eq(
        ops_mapping["floor"](df1.a),
        pd.Series([1.0, 2.0, 3.0]),
        check_names=False,
    )

    assert ops_mapping["abs"](-5) == 5
    assert ops_mapping["round"](1.234, 2) == 1.23
    assert ops_mapping["floor"](1.234) == 1


def test_string_operations():
    a = "a normal string"
    assert ops_mapping["characterlength"](a) == 15
    assert ops_mapping["upper"](a) == "A NORMAL STRING"
    assert ops_mapping["lower"](a) == "a normal string"
    assert ops_mapping["position"]("a", a, 4) == 7
    assert ops_mapping["position"]("ZL", a) == 0
    assert ops_mapping["trim"](a, "a") == " normal string"
    assert ops_mapping["btrim"](a, "a") == " normal string"
    assert ops_mapping["ltrim"](a, "a") == " normal string"
    assert ops_mapping["rtrim"](a, "a") == "a normal string"
    assert ops_mapping["overlay"](a, "XXX", 2) == "aXXXrmal string"
    assert ops_mapping["overlay"](a, "XXX", 2, 4) == "aXXXmal string"
    assert ops_mapping["overlay"](a, "XXX", 2, 1) == "aXXXnormal string"
    assert ops_mapping["substring"](a, -1) == "a normal string"
    assert ops_mapping["substring"](a, 10) == "string"
    assert ops_mapping["substring"](a, 2) == " normal string"
    assert ops_mapping["substring"](a, 2, 2) == " n"
    assert ops_mapping["initcap"](a) == "A Normal String"
    assert ops_mapping["replace"](a, "nor", "") == "a mal string"
    assert ops_mapping["replace"](a, "normal", "new") == "a new string"
    assert ops_mapping["replace"]("hello", "", "w") == "whwewlwlwow"


def test_dates():
    op = call.ExtractOperation()

    date = datetime.datetime(2021, 10, 3, 15, 53, 42, 47)
    assert int(op("CENTURY", date)) == 20
    assert op("DAY", date) == 3
    assert int(op("DECADE", date)) == 202
    assert op("DOW", date) == 0
    assert op("DOY", date) == 276
    assert op("HOUR", date) == 15
    assert op("MICROSECOND", date) == 47
    assert op("MILLENNIUM", date) == 2
    assert op("MILLISECOND", date) == 47000
    assert op("MINUTE", date) == 53
    assert op("MONTH", date) == 10
    assert op("QUARTER", date) == 4
    assert op("SECOND", date) == 42
    assert op("WEEK", date) == 39
    assert op("YEAR", date) == 2021
    assert op("DATE", date) == datetime.date(2021, 10, 3)

    ceil_op = call.CeilFloorOperation("ceil")
    floor_op = call.CeilFloorOperation("floor")

    assert ceil_op(date, "DAY") == datetime.datetime(2021, 10, 4)
    assert ceil_op(date, "HOUR") == datetime.datetime(2021, 10, 3, 16)
    assert ceil_op(date, "MINUTE") == datetime.datetime(2021, 10, 3, 15, 54)
    assert ceil_op(date, "SECOND") == datetime.datetime(2021, 10, 3, 15, 53, 43)
    assert ceil_op(date, "MILLISECOND") == datetime.datetime(
        2021, 10, 3, 15, 53, 42, 1000
    )

    assert floor_op(date, "DAY") == datetime.datetime(2021, 10, 3)
    assert floor_op(date, "HOUR") == datetime.datetime(2021, 10, 3, 15)
    assert floor_op(date, "MINUTE") == datetime.datetime(2021, 10, 3, 15, 53)
    assert floor_op(date, "SECOND") == datetime.datetime(2021, 10, 3, 15, 53, 42)
    assert floor_op(date, "MILLISECOND") == datetime.datetime(2021, 10, 3, 15, 53, 42)
