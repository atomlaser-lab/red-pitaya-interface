classdef RPJumperSetting
%RPJumperSetting defines constants used for specifying RP ADC jumper settings

    properties(Constant)
        LV = 0;
        HV = 1;
    end

    methods(Static)
        function label_out = match(value_in)
            p = properties(RPJumperSetting);
            label_out = p(value_in + 1);
            % label_out = {'', ''};
            % for pp = p'
            %     for nn = 1:numel(value_in)
            %         if RPJumperSetting.(pp{1}) == value_in(nn)
            %             label_out{nn} = pp{1};
            %         end
            %     end
            % end
            if isscalar(value_in)
                label_out = label_out{1};
                return
            end
            % for nn = 1:numel(label_out)
            %     if isempty(label_out{nn})
            %         error('Input value does not match jumper label!');
            %     end
            % end
        end
    end

end