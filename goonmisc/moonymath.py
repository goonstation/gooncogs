import functools

costs = {1: 0, 3: len("three "), 7: len("seven "), 13: len("thirteen "), 2: len("twice ")}

def moony_part(n, budget_list, cost):
    for num in [3, 7, 13]:
        if num > n:
            continue
        new_cost = cost + costs[num]
        if new_cost > budget_list[0]:
            continue
        for sub_result in moony_part(n // num, budget_list, new_cost):
            sub_result.append(num)
            yield sub_result
            sub_result.pop()
    yield []

@functools.cache
def moony_internal(n):
    if n < 0:
        return (None, float("inf"))
    if n == 0:
        return ([], 0)
    current_best = [float("inf")]
    result = None
    for multip in [2, 1]:
        mod_n = n // multip
        cur_cost_base = costs[multip]
        for part in moony_part(mod_n, current_best, cur_cost_base):
            if not len(part):
                continue
            part_mul = 1
            cur_cost = cur_cost_base
            for p in part:
                part_mul *= p
                cur_cost += costs[p]
            if cur_cost > current_best[0]:
                continue
            difference = n - multip * part_mul
            sub_result, sub_result_cost = moony_internal(difference)
            if sub_result is not None and len(sub_result) > 0:
                sub_result_cost += len("and ")
            if sub_result is not None and sub_result_cost + cur_cost < current_best[0]:
                our_group = None
                if multip != 1:
                    our_group = [multip] + part
                else:
                    our_group = part[:]
                result = sub_result + [our_group]
                current_best[0] = sub_result_cost + cur_cost
    return (result, current_best[0])

def moony_format(data, add_one):
    result = []
    if add_one == 1:
        if len(data) == 0:
            result.append("one")
        else:
            result.append("one more than")
    elif add_one == -1:
        result.append("one less than")
    for j, group in enumerate(data):
        is_last_group = j == len(data) - 1
        for i, elem in enumerate(group):
            is_last = i == len(group) - 1
            if not is_last:
                result.append({2: "twice", 3: "thrice", 7: "seven", 13: "thirteen"}[elem])
            else:
                result.append({3: "three", 7: "seven", 13: "thirteen"}[elem] + ("s" if len(group) > 1 else ""))
        if not is_last_group:
            result.append("and")
    return " ".join(result)

def moony_verify(n, data, add_one):
    n -= add_one
    for group in data:
        if not len(group):
            continue
        group_mul = 1
        for elem in group:
            group_mul *= elem
        n -= group_mul
    return n == 0

def moony(n):
    if not isinstance(n, int):
        return None
    if n <= 0:
        return None
    best_result = None
    best_cost = float("inf")
    for add_one, add_one_cost in [(0, 0), (1, len("one more than ")), (-1, len("one less than "))]:
        result, cost = moony_internal(n - add_one)
        if result is not None:
            assert moony_verify(n, result, add_one)
            if cost + add_one_cost < best_cost:
                best_cost = cost + add_one_cost
                best_result = (result, add_one)
    return moony_format(*best_result)
