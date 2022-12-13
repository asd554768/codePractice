class Solution {
public:
    int minFallingPathSum(vector<vector<int>>& matrix) {
        int row=matrix.size();
        int col=matrix[0].size();
        for(int i=1 ;i<row;i++){
            for(int j=0;j<col;j++){
                int val=INT_MAX;
                for(int k=max(0,j-1);k<=min(col-1,j+1);k++){
                    val=min(val,matrix[i-1][k]+matrix[i][j]);
                    /*
                    將上面一行與下面一行相加與其他路徑儲存的val比較
                    例如第一行第一個matrix[0][0]與第二行第一個matrix[1][0]相加與val(INT_MAX)比較
                    下一次第一行第一個matrix[0][0]與第二行matrix[1][1]第二個相加與val比較
                    */
                }
                matrix[i][j]=val;
                /*
                將最小的結果儲存在下一行(如同存在dp表格內)，再移動j
                當j移動完後再，移動i到下一行繼續相加直到找到最小
                */
            }
        }
        int res=INT_MAX;
        for(int i=0;i<col;i++){
            res=min(res,matrix[row-1][i]);
            //都儲存在最後一行了，所以找尋最後一行即是最小值
        }
        return res;
    }
};