class Solution {
public:
    bool canVisitAllRooms(vector<vector<int>>& rooms) {
        vector<bool> vec(rooms.size(),0);
        queue<int> q;
        vec[0]=true;
        /*for(int i=0;i<rooms[0].size();i++){
            q.push(rooms[0][i]);
        }*/
        q.push(0);
        while(!q.empty()){
            int goRoom=q.front();
            vec[goRoom]=true;
            q.pop();
            for(int i=0;i<rooms[goRoom].size();i++){
                if(!vec[rooms[goRoom][i]]){
                    q.push(rooms[goRoom][i]);
                }
                
            }
        }
        for(int i=0;i<vec.size();i++){
            if(vec[i]!=true) return false;
        }
        return true;
    }
};