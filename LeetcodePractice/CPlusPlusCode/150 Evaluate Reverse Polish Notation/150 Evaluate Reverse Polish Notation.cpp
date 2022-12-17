class Solution {
public:
    int evalRPN(vector<string>& tokens) {
        stack <string> st;
        long long val1;
        long long val2;
        for(int i=0;i<tokens.size();i++){
            if((tokens[i]=="+")||(tokens[i]=="*")||(tokens[i]=="/")||((tokens[i]=="-"))){
                if((tokens[i]=="+")){
                    val1=stoll(st.top());
                    st.pop();
                    val2=stoll(st.top());
                    st.pop();
                    st.push(to_string(val2+val1));
                }else if((tokens[i]=="*")){
                    val1=stoll(st.top());
                    st.pop();
                    val2=stoll(st.top());
                    st.pop();
                    st.push(to_string(val2*val1)); 
                }else if((tokens[i]=="/")){
                    val1=stoll(st.top());
                    st.pop();
                    val2=stoll(st.top());
                    st.pop();
                    st.push(to_string(val2/val1));  
                }else if((tokens[i]=="-")){
                    val1=stoll(st.top());
                    st.pop();
                    val2=stoll(st.top());
                    st.pop();
                    st.push(to_string(val2-val1));                      
                }
            }else{
                st.push(tokens[i]);
            }
        }
        
        return stoi(st.top());
    }
};