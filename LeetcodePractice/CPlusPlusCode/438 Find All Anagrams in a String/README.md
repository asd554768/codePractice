# 解說(mid)

## Sliding Window

* 將p和部分s加入hashtable(unordered_map)
* 先進行第一次比較
* 接下來移除left處的值(如果用hashtable還需要多移除如果是空的元素)
* 再來加入index內的值
* 重要關鍵是unordered_map或vector可以直接用==判斷相不相等