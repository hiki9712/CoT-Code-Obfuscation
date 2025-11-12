import os
import pickle
from statistics import stdev

import numpy as np

import hgm_utils



def get_num_total_evals():
    return hgm_utils.nodes[0].get_sum(lambda node: node.num_evals)


class Node:
    def __init__(
        self,
        node_id,
        score=None,
        verify_result=None,
        parent_id=None,
        child_ids=None,
        code=None,
        strategy=None,
        ori_code=None,
    ):
        self.node_id = node_id
        if child_ids is not None:
            self.child_ids = set(child_ids)
        else:
            self.child_ids = []
        self.score = score
        self.verify_result = verify_result
        self.parent_id = parent_id
        self.code = code
        self.strategy = strategy
        self.ori_code = ori_code
        hgm_utils.nodes[self.node_id] = self

    def get_sub_tree(self, fn=lambda self: self):
        if len(self.child_ids) == 0:
            return [fn(self)]
        else:
            nodes_list = [fn(self)]
            for child in self.child_ids:
                nodes_list.extend(child.get_sub_tree(fn))
            return nodes_list

    def get_pseudo_decendant_evals(self):
        return (
            self.score if self.num_evals < 10 else [self.mean_utility] * 10
        )

    def get_descendant_evals(self):
        #descendant_evals = [self.score]
        descendant_evals = [self.score] * 10
        for descendant in self.get_sub_tree():
            descendant_evals += [descendant.score]
        return descendant_evals

    @property
    def num_evals(self):
        return len(self.score)

    @property
    def mean_score(self):
        if self.num_evals == 0:
            return np.inf
        return np.sum(self.score) / self.num_evals

    def add_child(self, child):
        self.children.append(child)

    def save_as_dict(self):
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "strategy": self.strategy,
            "score": self.score,
            "code": self.code,
            "ori_code": self.ori_code,
            "verify_result": self.verify_result
        }
