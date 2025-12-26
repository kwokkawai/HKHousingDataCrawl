#!/usr/bin/env python3
"""测试面包屑解析逻辑"""
import re

def test_breadcrumb_parsing():
    """测试JavaScript paths的breadcrumb解析逻辑"""

    print("="*70)
    print("测试面包屑解析逻辑")
    print("="*70)

    # 模拟JavaScript paths内容（海之戀的例子）
    mock_paths_content = '''
    paths:[{name:bg,label:"主頁",params:{type:aS}},{name:bg,label:"買樓",params:{type:aS}},{name:bg,label:"新界西_4-NW",params:{type:aS}},{name:bg,label:"荃灣 | 麗城_23-WS050",params:{type:aS}},{name:bg,label:"荃灣西_19-HMA100",params:{type:aS}},{name:bg,label:"海之戀_2-DMXSZHLXHD",params:{type:aS}}]
    '''

    print(f"模拟的JavaScript paths内容: {mock_paths_content.strip()}")

    # 提取paths数组中的path字段（实际代码中的逻辑）
    paths_match = re.search(r'paths:\s*\[([^\]]+)\]', mock_paths_content)
    if paths_match:
        paths_content = paths_match.group(1)
        print(f"提取的paths内容: {paths_content}")

        # 解析paths数组中的path字段
        path_matches = re.findall(r'path:"([^"]+)"', paths_content)
        if not path_matches:
            # 如果没有path字段，尝试从label中提取
            path_matches = re.findall(r'label:"([^"]+)"', paths_content)

        print(f"提取的path_matches: {path_matches}")

        if path_matches:
            # 从path中提取实际的显示文本（去掉编码部分）
            breadcrumb_items = []
            for path in path_matches:
                # path格式如："新界西_4-NW", "荃灣 | 麗城_23-WS050", "荃景圍_19-HMA100"
                if '_' in path:
                    display_text = path.split('_')[0]
                    breadcrumb_items.append(display_text)
                else:
                    # 处理不带"_"的情况，如"買樓"
                    breadcrumb_items.append(path)

            print(f"解析后的breadcrumb_items: {breadcrumb_items}")

            # 映射面包屑项（修复后的逻辑）
            if len(breadcrumb_items) >= 4:
                # 初始化变量
                region = None
                district = None
                district_level2 = None
                sub_district = None
                estate_name = None

                # 查找区域信息（跳过"主頁"和"買樓"）
                for item in breadcrumb_items:
                    if any(keyword in item for keyword in ['新界', '港島', '九龍', '香港島']):
                        region = item
                        break

                # 获取非区域的项目
                non_region_items = [item for item in breadcrumb_items if item != region and item not in ['主頁', '買樓']]

                print(f"区域: {region}")
                print(f"非区域项目: {non_region_items}")

                if len(non_region_items) >= 3:
                    # district_level2（荃灣 | 麗城）
                    district_level2_candidate = non_region_items[0]
                    if '|' in district_level2_candidate:
                        district_level2 = district_level2_candidate
                        district = district_level2_candidate.split('|')[0].strip()
                    else:
                        district_level2 = district_level2_candidate

                    # sub_district（荃灣西）
                    sub_district_candidate = non_region_items[1]
                    if sub_district_candidate and sub_district_candidate != district_level2:
                        sub_district = sub_district_candidate

                    # estate_name（海之戀，修复后不要求"-"）
                    estate_name_candidate = non_region_items[2]
                    if estate_name_candidate:
                        estate_name = estate_name_candidate.lstrip('-').split('_')[0]

                print("\n" + "="*50)
                print("映射结果:")
                print("="*50)
                print(f"  region: {region}")
                print(f"  district: {district}")
                print(f"  district_level2: {district_level2}")
                print(f"  sub_district: {sub_district}")
                print(f"  estate_name: {estate_name}")

                # 验证结果
                expected = {
                    'region': '新界西',
                    'district': '荃灣',
                    'district_level2': '荃灣 | 麗城',
                    'sub_district': '荃灣西',
                    'estate_name': '海之戀'
                }

                print("\n" + "="*50)
                print("验证结果:")
                print("="*50)
                all_correct = True
                for key, expected_value in expected.items():
                    actual_value = locals().get(key)
                    status = "✓" if actual_value == expected_value else "✗"
                    if actual_value != expected_value:
                        all_correct = False
                    print(f"  {key}: {actual_value} {status} (期望: {expected_value})")

                print(f"\n總結: {'所有映射正確！' if all_correct else '部分映射有誤'}")

            else:
                print("✗ breadcrumb_items 長度不足")
        else:
            print("✗ 無法提取 path_matches")
    else:
        print("✗ 無法匹配 paths 內容")

if __name__ == "__main__":
    test_breadcrumb_parsing()
