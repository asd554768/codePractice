class Solution {
public:
    int minStoneSum(vector<int>& piles, int k) {
        priority_queue <int> q;
        int sum=0;
        for(int i=0;i<piles.size();i++){
            sum=sum+piles[i];
            q.push(piles[i]);
        }
        for(int i=0;i<k;i++){
            int topValue=q.top();
            q.pop();
            
            int afterValue=(int)((float)topValue/2+0.5);
            sum=sum-(topValue-afterValue);
            q.push(afterValue);
        }
        return sum;
    }
};