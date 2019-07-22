from collections import defaultdict
from typing import List, Optional

from samples_validator.base import ApiTestResult, CodeSample, HttpMethod


class TestExecutionResultMap:
    """
    Data structure for storing results of test runs for each code sample
    based on its HTTP resource path
    """

    def __init__(self):
        self._map = {}

    def put(self, test_result: ApiTestResult):
        self._put_test_result(
            self._map, test_result, path=test_result.sample.name,
        )

    def get_parent_result(self, sample: CodeSample) -> Optional[ApiTestResult]:
        return self._get_parent_test_result(
            self._map, sample, path=sample.name,
        )

    def get_parent_body(self, sample: CodeSample) -> dict:
        parent_result = self.get_parent_result(sample)
        if parent_result is not None:
            return parent_result.json_body or {}
        return {}

    def _put_test_result(
            self,
            current_dict: dict,
            test_result: ApiTestResult,
            path: str) -> dict:
        """
        Place test result in the maximum nested structure based on its path

        :param current_dict: Dict on current nesting level
        :param test_result: Result of running the code sample
        :param path: Path of the sample relative to current nesting level
        :return: Modified version of original dict containing the test_result

        For example, sample's path is 'a/b', then resulted dict will look like
        {'a': {'b': {'methods': {<HttpMethod.get: 'GET'>: ApiTestResult(..)}}}}
        """
        path_parts = path.split('/')
        current_path = path_parts[0]
        further_path = '/'.join(path_parts[1:])

        if not current_dict.get(current_path):
            current_dict[current_path] = defaultdict(dict)

        if not further_path:
            http_method = test_result.sample.http_method
            current_dict[current_path]['methods'][http_method] = test_result
        else:
            current_dict[current_path] = self._put_test_result(
                current_dict[current_path], test_result, further_path,
            )
        return current_dict

    def _get_parent_test_result(
            self,
            current_dict: dict,
            sample: CodeSample,
            path: str,
            current_parent: Optional[ApiTestResult] = None,
    ) -> Optional[ApiTestResult]:
        """
        Get the result of POST sample of parent resource in REST terminology.
        For example, we have a result of POST /parent. So for the
        /parent/{id} we want to get the result of previous request, mainly
        for substitution of the `id` param in the future

        :param current_dict: Dict on current nesting level
        :param sample: "Child" code sample
        :param path: Path of the sample relative to current nesting level
        :param current_parent: Current result of a method
        :return: Test result if it's present in the structure
        """

        path_parts = path.split('/')
        current_path = path_parts[0]
        further_path = '/'.join(path_parts[1:])

        current_methods = current_dict.get('methods', {})
        current_parent = current_methods.get(HttpMethod.post, current_parent)
        next_dict = current_dict.get(current_path)
        if not next_dict:
            return current_parent

        if not further_path:
            return current_parent
        else:
            return self._get_parent_test_result(
                next_dict, sample, further_path, current_parent,
            )


class CodeSamplesTree:
    """
    Data structure for storing code samples in a tree form based on
    HTTP resource path
    """

    def __init__(self):
        self._tree = {}

    def put(self, sample: CodeSample):
        self._put_code_sample(
            self._tree, f'{sample.lang.value}{sample.name}', sample,
        )

    def list_sorted_samples(self) -> List[CodeSample]:
        sorted_samples: List[CodeSample] = []
        self._sort_samples(self._tree, sorted_samples)
        return sorted_samples

    def _put_code_sample(self,
                         current_dict: dict,
                         path: str,
                         sample: CodeSample) -> dict:
        """
        Place code sample in the maximum nested structure based on its path

        :param current_dict: Dict on current nesting level
        :param path: Path of the sample relative to current nesting level
        :param sample: Code sample to put
        :return: Modified version of original dict containing the code sample

        For example, sample's path is 'a/b', then resulted dict will look like
        {'a': {'b': {'methods': {<HttpMethod.get: 'GET'>: CodeSample(..)}}}}
        """

        path_parts = path.split('/')
        current_path = path_parts[0]
        further_path = '/'.join(path_parts[1:])

        if not current_dict.get(current_path):
            current_dict[current_path] = defaultdict(dict)

        if not further_path:
            current_dict[current_path]['methods'][sample.http_method] = sample
        else:
            current_dict[current_path] = self._put_code_sample(
                current_dict[current_path], further_path, sample,
            )
        return current_dict

    def _sort_samples(
            self,
            endpoints: dict,
            result_list: List[CodeSample]):
        """
        DFS implementation for loading code samples from nested structure
        created by _put_code_sample method. It takes into account child-parent
        relations and sorting HTTP methods in logical order, e.g create parent,
        create child, delete child, delete parent.

        :param endpoints: Result of _put_code_sample function
        :param result_list: List to put sorted samples into
        :return: None. This function is mutate the result_list argument
        """

        methods = endpoints.get('methods', {})
        for method in (HttpMethod.post, HttpMethod.get, HttpMethod.put):
            if method in methods:
                result_list.append(methods[method])

        further_paths = [
            name for name in endpoints.keys() if name != 'methods'
        ]
        deepest_level = not further_paths

        if not deepest_level:
            for value in further_paths:
                self._sort_samples(endpoints[value], result_list)

        if HttpMethod.delete in methods:
            result_list.append(methods[HttpMethod.delete])