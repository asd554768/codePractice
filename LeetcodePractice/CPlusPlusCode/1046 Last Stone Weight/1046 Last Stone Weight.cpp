class Solution {
public:
    int lastStoneWeight(vector<int>& stones) {
        priority_queue<int>pq;
        for(int i=0;i<stones.size();i++){
            pq.push(stones[i]);
        }
        while(pq.size()>1){
            int front=pq.top();
            pq.pop();
            int end=pq.top();
            pq.pop();
            pq.push(front-end);
        }
        return pq.top();
    }
};