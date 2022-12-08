class Solution {
public:
string convert(string & s, int numRows)
{
    if (numRows == 1){
        return s;
    }
    string ret;
    int size = s.size();
    int jumplen = 2 * (numRows - 1); // 一個block移動次數
    ret.resize(s.size());
    int retpos = 0;//偏移量
    int spos = 0;
    int k = 0;
    for (int i = 0; i < numRows; ++i){
        spos = jumplen - 2 * i;
        spos = (spos>0) ? spos : jumplen;
        k = i;
        while (k< size){
            ret[retpos++] = s[k];
            k = k + spos;
            spos = (spos<jumplen) ? jumplen - spos : spos;
        }
    }
    return ret;
}
};