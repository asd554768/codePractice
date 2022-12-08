class Solution {
public:
    int counts[1024], nowMask;
    long long wonderfulSubstrings(string word) {
        long long total = 0;
        memset(counts, 0, sizeof(counts));
        counts[0] = 1; nowMask = 0;
        for (char &c : word) {
            nowMask ^= (1 << (c - 'a'));
            cout<<nowMask<<endl;
            total += counts[nowMask];
            //cout<<total<<endl;
            for (int i = 0; i < 10; ++i)
                total += counts[nowMask ^ (1 << i)];
            //cout<<"total: "<<total<<endl;
            ++counts[nowMask];
        }
        return total;
    }
};