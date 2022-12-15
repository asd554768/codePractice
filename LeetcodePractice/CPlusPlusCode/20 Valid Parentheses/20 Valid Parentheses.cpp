class Solution {
public:
    bool isValid(string s) {
        stack <char> st;
        if(s.size()==1) return false;
        st.push(s[0]);
        int i=1;
        while(i<s.size()){           
            if(st.empty()){
                st.push(s[i]);                
            }else{
                if(s[i]==')'){
                    if(st.top()!='('){                        
                        return false;
                    } 
                    else{
                        st.pop();
                    } 
                }else if(s[i]==']'){
                    if(st.top()!='[') return false;
                    else{                        
                        st.pop();                        
                    } 
                }else if(s[i]=='}'){
                    if(st.top()!='{') return false;
                    else st.pop();
                }else{
                    st.push(s[i]);
                }                                                
            }
            i++;            
        }
        if(!st.empty()) return false;
        return true; 
    }
};