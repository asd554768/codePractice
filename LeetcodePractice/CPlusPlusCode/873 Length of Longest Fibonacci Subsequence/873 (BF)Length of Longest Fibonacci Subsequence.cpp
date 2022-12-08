class Solution {
public:
    int lenLongestFibSubseq(vector<int>& arr) {
        int len=arr.size();
        int returnlen=0;
        unordered_set <int> uset(arr.begin(),arr.end());
        int ans=0;
        for(int i=0;i<len;i++){
            for(int j=i+1;j<len;j++){
                int x=arr[j],y=arr[i]+arr[j];
                returnlen=2;
                while(uset.find(y)!=uset.end()){
                    int z=x+y;//將原本前兩項相加準備下一次要找的值
                    x=y;//將原本的第二項變成下一次的第一項
                    y=z;//將剛剛相加的值變成下一次的第二項
                    ans=max(ans,++returnlen);
                }
            }
        }
        return ans>=3?ans:0;
    }
};