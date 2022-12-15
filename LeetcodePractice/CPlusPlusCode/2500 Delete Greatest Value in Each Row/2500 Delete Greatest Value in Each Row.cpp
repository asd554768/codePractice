class Solution {
public:
    int deleteGreatestValue(vector<vector<int>>& grid) {
        int sum=0;
        for(int j=0;j<grid.size();j++){
            sort(grid[j].begin(),grid[j].end());
        }        
        for(int i=0;i<grid[0].size();i++){
            int max=0;
            for(int j=0;j<grid.size();j++){                
                max=grid[j][i]>max?grid[j][i]:max;
            }
            sum+=max;
        }
        return sum;
    }
};