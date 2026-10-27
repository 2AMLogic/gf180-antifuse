module antifuse_digital_top (busy,
    clk,
    cs_n,
    miso,
    miso_oe,
    mosi,
    prog_en,
    read_en,
    rst_n,
    sclk,
    sense_in,
    col_onehot,
    col_sel,
    row_onehot,
    row_sel);
 output busy;
 input clk;
 input cs_n;
 output miso;
 output miso_oe;
 input mosi;
 output prog_en;
 output read_en;
 input rst_n;
 input sclk;
 input sense_in;
 output [31:0] col_onehot;
 output [4:0] col_sel;
 output [31:0] row_onehot;
 output [4:0] row_sel;

 wire dec_en;
 wire \u_col_dec/_00_ ;
 wire \u_col_dec/_01_ ;
 wire \u_col_dec/_02_ ;
 wire \u_col_dec/_03_ ;
 wire clknet_0_clk;
 wire \u_col_dec/_05_ ;
 wire \u_col_dec/_06_ ;
 wire \u_col_dec/_07_ ;
 wire \u_col_dec/_08_ ;
 wire \u_col_dec/_09_ ;
 wire \u_col_dec/_10_ ;
 wire \u_col_dec/_11_ ;
 wire \u_col_dec/_12_ ;
 wire \u_col_dec/_13_ ;
 wire \u_col_dec/_14_ ;
 wire \u_col_dec/_15_ ;
 wire \u_col_dec/_16_ ;
 wire \u_col_dec/_17_ ;
 wire \u_col_dec/_18_ ;
 wire \u_col_dec/_19_ ;
 wire \u_col_dec/_20_ ;
 wire \u_col_dec/_21_ ;
 wire clknet_3_0__leaf_clk;
 wire \u_regs/_000_ ;
 wire \u_regs/_001_ ;
 wire \u_regs/_002_ ;
 wire \u_regs/_003_ ;
 wire \u_regs/_004_ ;
 wire \u_regs/_005_ ;
 wire \u_regs/_006_ ;
 wire \u_regs/_007_ ;
 wire \u_regs/_008_ ;
 wire \u_regs/_009_ ;
 wire \u_regs/_010_ ;
 wire \u_regs/_011_ ;
 wire \u_regs/_012_ ;
 wire \u_regs/_013_ ;
 wire \u_regs/_014_ ;
 wire \u_regs/_015_ ;
 wire \u_regs/_016_ ;
 wire \u_regs/_017_ ;
 wire \u_regs/_018_ ;
 wire \u_regs/_019_ ;
 wire \u_regs/_020_ ;
 wire \u_regs/_021_ ;
 wire \u_regs/_022_ ;
 wire \u_regs/_023_ ;
 wire \u_regs/_024_ ;
 wire \u_regs/_025_ ;
 wire \u_regs/_026_ ;
 wire \u_regs/_027_ ;
 wire \u_regs/_028_ ;
 wire \u_regs/_029_ ;
 wire \u_regs/_030_ ;
 wire \u_regs/_031_ ;
 wire \u_regs/_032_ ;
 wire \u_regs/_033_ ;
 wire \u_regs/_034_ ;
 wire \u_regs/_035_ ;
 wire \u_regs/_036_ ;
 wire \u_regs/_037_ ;
 wire \u_regs/_038_ ;
 wire \u_regs/_039_ ;
 wire \u_regs/_040_ ;
 wire \u_regs/_041_ ;
 wire \u_regs/_042_ ;
 wire \u_regs/_043_ ;
 wire \u_regs/_044_ ;
 wire \u_regs/_045_ ;
 wire \u_regs/_046_ ;
 wire \u_regs/_047_ ;
 wire \u_regs/_048_ ;
 wire \u_regs/_049_ ;
 wire \u_regs/_050_ ;
 wire \u_regs/_051_ ;
 wire \u_regs/_052_ ;
 wire \u_regs/_053_ ;
 wire \u_regs/_054_ ;
 wire \u_regs/_055_ ;
 wire \u_regs/_056_ ;
 wire \u_regs/_057_ ;
 wire \u_regs/_058_ ;
 wire \u_regs/_059_ ;
 wire \u_regs/_060_ ;
 wire \u_regs/_061_ ;
 wire \u_regs/_062_ ;
 wire \u_regs/_063_ ;
 wire \u_regs/_064_ ;
 wire \u_regs/_065_ ;
 wire \u_regs/_066_ ;
 wire \u_regs/_067_ ;
 wire \u_regs/_068_ ;
 wire \u_regs/_069_ ;
 wire \u_regs/_070_ ;
 wire \u_regs/_071_ ;
 wire \u_regs/_072_ ;
 wire \u_regs/_073_ ;
 wire \u_regs/_074_ ;
 wire \u_regs/_075_ ;
 wire \u_regs/_076_ ;
 wire \u_regs/_077_ ;
 wire \u_regs/_078_ ;
 wire \u_regs/_079_ ;
 wire \u_regs/_080_ ;
 wire \u_regs/_081_ ;
 wire \u_regs/_082_ ;
 wire \u_regs/_083_ ;
 wire \u_regs/_084_ ;
 wire \u_regs/_085_ ;
 wire \u_regs/_086_ ;
 wire \u_regs/_087_ ;
 wire \u_regs/_088_ ;
 wire \u_regs/_089_ ;
 wire \u_regs/_090_ ;
 wire \u_regs/_091_ ;
 wire \u_regs/_092_ ;
 wire \u_regs/_093_ ;
 wire \u_regs/_094_ ;
 wire \u_regs/_095_ ;
 wire \u_regs/_096_ ;
 wire \u_regs/_097_ ;
 wire \u_regs/_098_ ;
 wire \u_regs/_099_ ;
 wire \u_regs/_100_ ;
 wire \u_regs/_101_ ;
 wire \u_regs/_102_ ;
 wire \u_regs/_103_ ;
 wire \u_regs/_104_ ;
 wire \u_regs/_105_ ;
 wire \u_regs/_106_ ;
 wire \u_regs/_107_ ;
 wire \u_regs/_108_ ;
 wire \u_regs/_109_ ;
 wire \u_regs/_110_ ;
 wire \u_regs/_111_ ;
 wire \u_regs/_112_ ;
 wire \u_regs/_113_ ;
 wire \u_regs/_114_ ;
 wire \u_regs/_115_ ;
 wire \u_regs/_116_ ;
 wire \u_regs/_117_ ;
 wire \u_regs/_118_ ;
 wire \u_regs/_119_ ;
 wire \u_regs/_120_ ;
 wire \u_regs/_121_ ;
 wire \u_regs/_122_ ;
 wire \u_regs/_123_ ;
 wire \u_regs/_124_ ;
 wire \u_regs/_125_ ;
 wire \u_regs/_126_ ;
 wire \u_regs/_127_ ;
 wire \u_regs/_128_ ;
 wire \u_regs/_129_ ;
 wire \u_regs/_130_ ;
 wire \u_regs/_131_ ;
 wire \u_regs/_132_ ;
 wire \u_regs/_133_ ;
 wire \u_regs/_134_ ;
 wire \u_regs/_135_ ;
 wire \u_regs/_136_ ;
 wire \u_regs/_137_ ;
 wire \u_regs/_138_ ;
 wire \u_regs/_139_ ;
 wire \u_regs/_140_ ;
 wire \u_regs/_141_ ;
 wire \u_regs/_142_ ;
 wire \u_regs/_143_ ;
 wire \u_regs/_144_ ;
 wire \u_regs/_145_ ;
 wire \u_regs/_146_ ;
 wire \u_regs/_147_ ;
 wire \u_regs/_148_ ;
 wire \u_regs/_149_ ;
 wire clknet_3_3__leaf_clk;
 wire \u_regs/_151_ ;
 wire \u_regs/_152_ ;
 wire \u_regs/_153_ ;
 wire \u_regs/_154_ ;
 wire \u_regs/_155_ ;
 wire \u_regs/_156_ ;
 wire \u_regs/_157_ ;
 wire \u_regs/_158_ ;
 wire \u_regs/_159_ ;
 wire \u_regs/_160_ ;
 wire clknet_3_4__leaf_clk;
 wire \u_regs/_162_ ;
 wire \u_regs/_163_ ;
 wire \u_regs/_164_ ;
 wire \u_regs/_165_ ;
 wire \u_regs/_166_ ;
 wire \u_regs/_167_ ;
 wire \u_regs/_168_ ;
 wire \u_regs/_169_ ;
 wire \u_regs/_170_ ;
 wire \u_regs/_171_ ;
 wire \u_regs/_172_ ;
 wire \u_regs/_173_ ;
 wire \u_regs/_174_ ;
 wire \u_regs/_175_ ;
 wire \u_regs/_176_ ;
 wire \u_regs/_177_ ;
 wire \u_regs/_178_ ;
 wire \u_regs/_179_ ;
 wire \u_regs/_180_ ;
 wire \u_regs/_181_ ;
 wire \u_regs/_182_ ;
 wire \u_regs/_183_ ;
 wire \u_regs/_184_ ;
 wire \u_regs/_185_ ;
 wire \u_regs/_186_ ;
 wire \u_regs/_187_ ;
 wire \u_regs/_188_ ;
 wire \u_regs/_189_ ;
 wire \u_regs/_190_ ;
 wire \u_regs/_191_ ;
 wire \u_regs/_192_ ;
 wire \u_regs/_193_ ;
 wire \u_regs/_194_ ;
 wire \u_regs/_195_ ;
 wire \u_regs/_196_ ;
 wire \u_regs/_197_ ;
 wire \u_regs/_198_ ;
 wire \u_regs/_199_ ;
 wire \u_regs/_200_ ;
 wire \u_regs/_201_ ;
 wire \u_regs/_202_ ;
 wire \u_regs/_203_ ;
 wire \u_regs/_204_ ;
 wire \u_regs/_205_ ;
 wire \u_regs/_206_ ;
 wire \u_regs/_207_ ;
 wire \u_regs/_208_ ;
 wire \u_regs/_209_ ;
 wire \u_regs/_210_ ;
 wire \u_regs/_211_ ;
 wire \u_regs/_212_ ;
 wire \u_regs/_213_ ;
 wire \u_regs/_214_ ;
 wire \u_regs/_215_ ;
 wire \u_regs/_216_ ;
 wire \u_regs/_217_ ;
 wire \u_regs/_218_ ;
 wire \u_regs/_219_ ;
 wire \u_regs/_220_ ;
 wire \u_regs/_221_ ;
 wire \u_regs/_222_ ;
 wire \u_regs/_223_ ;
 wire \u_regs/_224_ ;
 wire \u_regs/_225_ ;
 wire \u_regs/_226_ ;
 wire \u_regs/_227_ ;
 wire \u_regs/_228_ ;
 wire \u_regs/_229_ ;
 wire \u_regs/_230_ ;
 wire \u_regs/_231_ ;
 wire \u_regs/_232_ ;
 wire \u_regs/_233_ ;
 wire \u_regs/_234_ ;
 wire \u_regs/_235_ ;
 wire \u_regs/_236_ ;
 wire \u_regs/_237_ ;
 wire \u_regs/_238_ ;
 wire \u_regs/_239_ ;
 wire \u_regs/_240_ ;
 wire \u_regs/_241_ ;
 wire \u_regs/_242_ ;
 wire \u_regs/_243_ ;
 wire \u_regs/_244_ ;
 wire \u_regs/_245_ ;
 wire \u_regs/_246_ ;
 wire \u_regs/_247_ ;
 wire \u_regs/_248_ ;
 wire \u_regs/_249_ ;
 wire \u_regs/_250_ ;
 wire \u_regs/_251_ ;
 wire \u_regs/_252_ ;
 wire \u_regs/_253_ ;
 wire \u_regs/_254_ ;
 wire \u_regs/_255_ ;
 wire \u_regs/_256_ ;
 wire \u_regs/_257_ ;
 wire \u_regs/_258_ ;
 wire \u_regs/_259_ ;
 wire \u_regs/_260_ ;
 wire \u_regs/_261_ ;
 wire \u_regs/_262_ ;
 wire \u_regs/_263_ ;
 wire \u_regs/_264_ ;
 wire \u_regs/_265_ ;
 wire \u_regs/_266_ ;
 wire \u_regs/_267_ ;
 wire \u_regs/_268_ ;
 wire \u_regs/_269_ ;
 wire \u_regs/_270_ ;
 wire \u_regs/_271_ ;
 wire \u_regs/_272_ ;
 wire \u_regs/_273_ ;
 wire \u_regs/_274_ ;
 wire \u_regs/_275_ ;
 wire \u_regs/_276_ ;
 wire \u_regs/_277_ ;
 wire \u_regs/_278_ ;
 wire \u_regs/_279_ ;
 wire \u_regs/_280_ ;
 wire \u_regs/_281_ ;
 wire \u_regs/_282_ ;
 wire \u_regs/_283_ ;
 wire \u_regs/_284_ ;
 wire \u_regs/_285_ ;
 wire \u_regs/_286_ ;
 wire \u_regs/_287_ ;
 wire \u_regs/_288_ ;
 wire \u_regs/_289_ ;
 wire \u_regs/_290_ ;
 wire \u_regs/_291_ ;
 wire \u_regs/_292_ ;
 wire \u_regs/_293_ ;
 wire \u_regs/_294_ ;
 wire \u_regs/_295_ ;
 wire \u_regs/_296_ ;
 wire \u_regs/_297_ ;
 wire \u_regs/_298_ ;
 wire \u_regs/_299_ ;
 wire \u_regs/_300_ ;
 wire \u_regs/_301_ ;
 wire \u_regs/_302_ ;
 wire \u_regs/_303_ ;
 wire \u_regs/_304_ ;
 wire \u_regs/_305_ ;
 wire \u_regs/_306_ ;
 wire \u_regs/_307_ ;
 wire \u_regs/_308_ ;
 wire \u_regs/_309_ ;
 wire \u_regs/_310_ ;
 wire \u_regs/_311_ ;
 wire \u_regs/_312_ ;
 wire \u_regs/_313_ ;
 wire \u_regs/_314_ ;
 wire \u_regs/_315_ ;
 wire \u_regs/_316_ ;
 wire \u_regs/_317_ ;
 wire \u_regs/_318_ ;
 wire \u_regs/_319_ ;
 wire \u_regs/_320_ ;
 wire \u_regs/_321_ ;
 wire \u_regs/arm ;
 wire \u_regs/cs_1 ;
 wire \u_regs/cs_2 ;
 wire \u_regs/cs_d ;
 wire \u_regs/miso_r ;
 wire \u_regs/mosi_1 ;
 wire \u_regs/mosi_2 ;
 wire \u_regs/perr ;
 wire \u_regs/prog_done ;
 wire \u_regs/rdata ;
 wire \u_regs/read_valid ;
 wire \u_regs/rs1 ;
 wire \u_regs/rst_s ;
 wire \u_regs/sck_1 ;
 wire \u_regs/sck_2 ;
 wire \u_regs/sck_d ;
 wire \u_regs/sns_1 ;
 wire \u_regs/sns_2 ;
 wire \u_row_dec/_00_ ;
 wire \u_row_dec/_01_ ;
 wire \u_row_dec/_02_ ;
 wire \u_row_dec/_03_ ;
 wire clknet_3_1__leaf_clk;
 wire \u_row_dec/_05_ ;
 wire \u_row_dec/_06_ ;
 wire \u_row_dec/_07_ ;
 wire \u_row_dec/_08_ ;
 wire \u_row_dec/_09_ ;
 wire \u_row_dec/_10_ ;
 wire \u_row_dec/_11_ ;
 wire \u_row_dec/_12_ ;
 wire \u_row_dec/_13_ ;
 wire \u_row_dec/_14_ ;
 wire \u_row_dec/_15_ ;
 wire \u_row_dec/_16_ ;
 wire \u_row_dec/_17_ ;
 wire \u_row_dec/_18_ ;
 wire \u_row_dec/_19_ ;
 wire \u_row_dec/_20_ ;
 wire \u_row_dec/_21_ ;
 wire clknet_3_2__leaf_clk;
 wire \u_regs/net3 ;
 wire clknet_3_5__leaf_clk;
 wire clknet_3_6__leaf_clk;
 wire clknet_3_7__leaf_clk;
 wire [12:0] \u_regs/arm_cnt ;
 wire [4:0] \u_regs/bitcnt ;
 wire [7:0] \u_regs/cmd ;
 wire [7:0] \u_regs/dat ;
 wire [7:0] \u_regs/pw_cnt ;
 wire [7:0] \u_regs/pw_r ;
 wire [7:0] \u_regs/rd_byte ;
 wire [7:0] \u_regs/rd_cnt ;

 gf180mcu_fd_sc_mcu7t5v0__or2_4 _0_ (.A1(prog_en),
    .A2(read_en),
    .Z(dec_en));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_0_clk (.I(clk),
    .Z(clknet_0_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_0__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_0__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_1__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_1__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_2__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_2__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_3__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_3__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_4__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_4__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_5__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_5__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_6__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_6__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__buf_4 clkbuf_3_7__f_clk (.I(clknet_0_clk),
    .Z(clknet_3_7__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_8 clkload0 (.I(clknet_3_0__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 clkload1 (.I(clknet_3_1__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_8 clkload2 (.I(clknet_3_2__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 clkload3 (.I(clknet_3_3__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 clkload4 (.I(clknet_3_4__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_2 clkload5 (.I(clknet_3_5__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_2 clkload6 (.I(clknet_3_6__leaf_clk));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_col_dec/_23_  (.A1(col_sel[0]),
    .A2(col_sel[1]),
    .ZN(\u_col_dec/_00_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_col_dec/_24_  (.A1(col_sel[3]),
    .A2(col_sel[2]),
    .ZN(\u_col_dec/_01_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_2 \u_col_dec/_25_  (.A1(\u_col_dec/_00_ ),
    .A2(\u_col_dec/_01_ ),
    .Z(\u_col_dec/_02_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_col_dec/_26_  (.A1(col_sel[4]),
    .A2(dec_en),
    .ZN(\u_col_dec/_03_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_col_dec/_28_  (.A1(\u_col_dec/_02_ ),
    .A2(\u_col_dec/_03_ ),
    .ZN(col_onehot[31]));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_4 \u_col_dec/_29_  (.I(col_sel[0]),
    .ZN(\u_col_dec/_05_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_col_dec/_30_  (.A1(\u_col_dec/_05_ ),
    .A2(col_sel[1]),
    .ZN(\u_col_dec/_06_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_31_  (.A1(\u_col_dec/_01_ ),
    .A2(\u_col_dec/_03_ ),
    .A3(\u_col_dec/_06_ ),
    .ZN(col_onehot[30]));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 \u_col_dec/_32_  (.I(col_sel[1]),
    .ZN(\u_col_dec/_07_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_col_dec/_33_  (.A1(col_sel[0]),
    .A2(\u_col_dec/_07_ ),
    .ZN(\u_col_dec/_08_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_34_  (.A1(\u_col_dec/_01_ ),
    .A2(\u_col_dec/_03_ ),
    .A3(\u_col_dec/_08_ ),
    .ZN(col_onehot[29]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_col_dec/_35_  (.A1(col_sel[0]),
    .A2(col_sel[1]),
    .ZN(\u_col_dec/_09_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_col_dec/_36_  (.A1(col_sel[3]),
    .A2(col_sel[2]),
    .A3(\u_col_dec/_09_ ),
    .ZN(\u_col_dec/_10_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_col_dec/_37_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_10_ ),
    .ZN(col_onehot[28]));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 \u_col_dec/_38_  (.I(col_sel[2]),
    .ZN(\u_col_dec/_11_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_col_dec/_39_  (.A1(col_sel[3]),
    .A2(\u_col_dec/_11_ ),
    .ZN(\u_col_dec/_12_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_40_  (.A1(\u_col_dec/_00_ ),
    .A2(\u_col_dec/_03_ ),
    .A3(\u_col_dec/_12_ ),
    .ZN(col_onehot[27]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_41_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_06_ ),
    .A3(\u_col_dec/_12_ ),
    .ZN(col_onehot[26]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_42_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_08_ ),
    .A3(\u_col_dec/_12_ ),
    .ZN(col_onehot[25]));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_col_dec/_43_  (.A1(\u_col_dec/_05_ ),
    .A2(\u_col_dec/_07_ ),
    .ZN(\u_col_dec/_13_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_44_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_13_ ),
    .A3(\u_col_dec/_12_ ),
    .ZN(col_onehot[24]));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_3 \u_col_dec/_45_  (.I(col_sel[3]),
    .ZN(\u_col_dec/_14_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_col_dec/_46_  (.A1(\u_col_dec/_14_ ),
    .A2(col_sel[2]),
    .ZN(\u_col_dec/_15_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_47_  (.A1(\u_col_dec/_00_ ),
    .A2(\u_col_dec/_03_ ),
    .A3(\u_col_dec/_15_ ),
    .ZN(col_onehot[23]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_48_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_06_ ),
    .A3(\u_col_dec/_15_ ),
    .ZN(col_onehot[22]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_49_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_08_ ),
    .A3(\u_col_dec/_15_ ),
    .ZN(col_onehot[21]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_50_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_13_ ),
    .A3(\u_col_dec/_15_ ),
    .ZN(col_onehot[20]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_col_dec/_51_  (.A1(col_sel[3]),
    .A2(col_sel[2]),
    .ZN(\u_col_dec/_16_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_col_dec/_52_  (.A1(col_sel[0]),
    .A2(col_sel[1]),
    .A3(\u_col_dec/_16_ ),
    .ZN(\u_col_dec/_17_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_col_dec/_53_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_17_ ),
    .ZN(col_onehot[19]));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_col_dec/_54_  (.A1(\u_col_dec/_14_ ),
    .A2(\u_col_dec/_11_ ),
    .ZN(\u_col_dec/_18_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_55_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_06_ ),
    .A3(\u_col_dec/_18_ ),
    .ZN(col_onehot[18]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_56_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_08_ ),
    .A3(\u_col_dec/_18_ ),
    .ZN(col_onehot[17]));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_col_dec/_57_  (.A1(\u_col_dec/_09_ ),
    .A2(\u_col_dec/_16_ ),
    .ZN(\u_col_dec/_19_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_col_dec/_58_  (.A1(\u_col_dec/_03_ ),
    .A2(\u_col_dec/_19_ ),
    .ZN(col_onehot[16]));
 gf180mcu_fd_sc_mcu7t5v0__inv_3 \u_col_dec/_59_  (.I(col_sel[4]),
    .ZN(\u_col_dec/_20_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_col_dec/_60_  (.A1(\u_col_dec/_20_ ),
    .A2(dec_en),
    .ZN(\u_col_dec/_21_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_col_dec/_62_  (.A1(\u_col_dec/_02_ ),
    .A2(\u_col_dec/_21_ ),
    .ZN(col_onehot[15]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_4 \u_col_dec/_63_  (.A1(\u_col_dec/_01_ ),
    .A2(\u_col_dec/_06_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[14]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_col_dec/_64_  (.A1(\u_col_dec/_01_ ),
    .A2(\u_col_dec/_08_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[13]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_col_dec/_65_  (.A1(\u_col_dec/_10_ ),
    .A2(\u_col_dec/_21_ ),
    .ZN(col_onehot[12]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_col_dec/_66_  (.A1(\u_col_dec/_00_ ),
    .A2(\u_col_dec/_12_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[11]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_col_dec/_67_  (.A1(\u_col_dec/_06_ ),
    .A2(\u_col_dec/_12_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[10]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_4 \u_col_dec/_68_  (.A1(\u_col_dec/_08_ ),
    .A2(\u_col_dec/_12_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[9]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_col_dec/_69_  (.A1(\u_col_dec/_13_ ),
    .A2(\u_col_dec/_12_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[8]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_70_  (.A1(\u_col_dec/_00_ ),
    .A2(\u_col_dec/_15_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[7]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_71_  (.A1(\u_col_dec/_06_ ),
    .A2(\u_col_dec/_15_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[6]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_72_  (.A1(\u_col_dec/_08_ ),
    .A2(\u_col_dec/_15_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[5]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_73_  (.A1(\u_col_dec/_13_ ),
    .A2(\u_col_dec/_15_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[4]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_col_dec/_74_  (.A1(\u_col_dec/_17_ ),
    .A2(\u_col_dec/_21_ ),
    .ZN(col_onehot[3]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_75_  (.A1(\u_col_dec/_06_ ),
    .A2(\u_col_dec/_18_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[2]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_col_dec/_76_  (.A1(\u_col_dec/_08_ ),
    .A2(\u_col_dec/_18_ ),
    .A3(\u_col_dec/_21_ ),
    .ZN(col_onehot[1]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_col_dec/_77_  (.A1(\u_col_dec/_19_ ),
    .A2(\u_col_dec/_21_ ),
    .ZN(col_onehot[0]));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_322_  (.I(\u_regs/cs_2 ),
    .ZN(miso_oe));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_323_  (.A1(prog_en),
    .A2(read_en),
    .ZN(\u_regs/_084_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_324_  (.I(\u_regs/_084_ ),
    .ZN(busy));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_325_  (.I(\u_regs/arm ),
    .ZN(\u_regs/_085_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_326_  (.I(\u_regs/pw_cnt [1]),
    .ZN(\u_regs/_086_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_327_  (.A1(\u_regs/pw_cnt [2]),
    .A2(\u_regs/pw_cnt [5]),
    .A3(\u_regs/pw_cnt [6]),
    .A4(\u_regs/pw_cnt [7]),
    .ZN(\u_regs/_087_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_328_  (.A1(\u_regs/pw_cnt [3]),
    .A2(\u_regs/pw_cnt [4]),
    .ZN(\u_regs/_088_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_329_  (.A1(\u_regs/pw_cnt [0]),
    .A2(\u_regs/_086_ ),
    .A3(\u_regs/_087_ ),
    .A4(\u_regs/_088_ ),
    .ZN(\u_regs/_089_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_330_  (.A1(prog_en),
    .A2(\u_regs/_089_ ),
    .ZN(\u_regs/_090_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_331_  (.A1(\u_regs/_085_ ),
    .A2(\u_regs/_090_ ),
    .ZN(\u_regs/_091_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_332_  (.I(\u_regs/cs_d ),
    .ZN(\u_regs/_092_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_333_  (.A1(\u_regs/bitcnt [3]),
    .A2(\u_regs/bitcnt [2]),
    .A3(\u_regs/bitcnt [1]),
    .A4(\u_regs/bitcnt [0]),
    .ZN(\u_regs/_093_ ));
 gf180mcu_fd_sc_mcu7t5v0__and4_1 \u_regs/_334_  (.A1(\u_regs/cs_2 ),
    .A2(\u_regs/_092_ ),
    .A3(\u_regs/bitcnt [4]),
    .A4(\u_regs/_093_ ),
    .Z(\u_regs/_094_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_335_  (.A1(\u_regs/cmd [4]),
    .A2(\u_regs/cmd [5]),
    .A3(\u_regs/cmd [3]),
    .ZN(\u_regs/_095_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_336_  (.A1(\u_regs/cmd [6]),
    .A2(\u_regs/cmd [7]),
    .ZN(\u_regs/_096_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_337_  (.A1(\u_regs/cmd [1]),
    .A2(\u_regs/cmd [2]),
    .ZN(\u_regs/_097_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_338_  (.A1(\u_regs/_095_ ),
    .A2(\u_regs/_096_ ),
    .A3(\u_regs/_097_ ),
    .ZN(\u_regs/_098_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_339_  (.A1(\u_regs/_094_ ),
    .A2(\u_regs/_098_ ),
    .Z(\u_regs/_099_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_340_  (.I(\u_regs/cmd [2]),
    .ZN(\u_regs/_100_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_341_  (.A1(\u_regs/cmd [4]),
    .A2(\u_regs/cmd [5]),
    .A3(\u_regs/cmd [3]),
    .A4(\u_regs/cmd [6]),
    .ZN(\u_regs/_101_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_342_  (.A1(\u_regs/cmd [1]),
    .A2(\u_regs/_100_ ),
    .A3(\u_regs/cmd [0]),
    .A4(\u_regs/_101_ ),
    .ZN(\u_regs/_102_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_343_  (.A1(\u_regs/cmd [1]),
    .A2(\u_regs/cmd [2]),
    .ZN(\u_regs/_103_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_344_  (.A1(\u_regs/_101_ ),
    .A2(\u_regs/_103_ ),
    .ZN(\u_regs/_104_ ));
 gf180mcu_fd_sc_mcu7t5v0__or3_1 \u_regs/_345_  (.A1(\u_regs/dat [6]),
    .A2(\u_regs/dat [5]),
    .A3(\u_regs/dat [7]),
    .Z(\u_regs/_105_ ));
 gf180mcu_fd_sc_mcu7t5v0__or3_1 \u_regs/_346_  (.A1(\u_regs/dat [1]),
    .A2(\u_regs/dat [2]),
    .A3(\u_regs/dat [0]),
    .Z(\u_regs/_106_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_347_  (.A1(\u_regs/dat [3]),
    .A2(\u_regs/dat [4]),
    .A3(\u_regs/_105_ ),
    .A4(\u_regs/_106_ ),
    .ZN(\u_regs/_107_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_348_  (.A1(\u_regs/_104_ ),
    .A2(\u_regs/_107_ ),
    .B(\u_regs/arm ),
    .ZN(\u_regs/_108_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_349_  (.A1(\u_regs/_102_ ),
    .A2(\u_regs/_108_ ),
    .Z(\u_regs/_109_ ));
 gf180mcu_fd_sc_mcu7t5v0__or3_2 \u_regs/_350_  (.A1(\u_regs/dat [3]),
    .A2(\u_regs/dat [4]),
    .A3(\u_regs/_105_ ),
    .Z(\u_regs/_110_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_351_  (.A1(\u_regs/dat [1]),
    .A2(\u_regs/dat [2]),
    .ZN(\u_regs/_111_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_352_  (.A1(\u_regs/dat [0]),
    .A2(\u_regs/_111_ ),
    .ZN(\u_regs/_112_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_353_  (.A1(\u_regs/dat [1]),
    .A2(\u_regs/dat [0]),
    .ZN(\u_regs/_113_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_354_  (.A1(\u_regs/dat [2]),
    .A2(\u_regs/_113_ ),
    .ZN(\u_regs/_114_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_355_  (.A1(\u_regs/_112_ ),
    .A2(\u_regs/_114_ ),
    .B(\u_regs/_085_ ),
    .ZN(\u_regs/_115_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_356_  (.A1(\u_regs/dat [2]),
    .A2(\u_regs/dat [0]),
    .B(\u_regs/dat [1]),
    .ZN(\u_regs/_116_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_357_  (.I(\u_regs/_116_ ),
    .ZN(\u_regs/_117_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_358_  (.I(\u_regs/cmd [0]),
    .ZN(\u_regs/_118_ ));
 gf180mcu_fd_sc_mcu7t5v0__and3_1 \u_regs/_359_  (.A1(\u_regs/cmd [1]),
    .A2(\u_regs/_100_ ),
    .A3(\u_regs/_118_ ),
    .Z(\u_regs/_119_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_360_  (.A1(\u_regs/_101_ ),
    .A2(\u_regs/_119_ ),
    .Z(\u_regs/_120_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai31_1 \u_regs/_361_  (.A1(\u_regs/_110_ ),
    .A2(\u_regs/_115_ ),
    .A3(\u_regs/_117_ ),
    .B(\u_regs/_120_ ),
    .ZN(\u_regs/_121_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_362_  (.A1(\u_regs/cs_2 ),
    .A2(\u_regs/_092_ ),
    .ZN(\u_regs/_122_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_363_  (.A1(\u_regs/_122_ ),
    .A2(\u_regs/_093_ ),
    .ZN(\u_regs/_123_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_364_  (.A1(\u_regs/cmd [5]),
    .A2(\u_regs/cmd [3]),
    .A3(\u_regs/cmd [6]),
    .A4(\u_regs/_118_ ),
    .ZN(\u_regs/_124_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_365_  (.A1(\u_regs/arm ),
    .A2(\u_regs/cmd [4]),
    .A3(\u_regs/_103_ ),
    .ZN(\u_regs/_125_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_366_  (.I(\u_regs/cmd [6]),
    .ZN(\u_regs/_126_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_367_  (.A1(\u_regs/_126_ ),
    .A2(\u_regs/_095_ ),
    .ZN(\u_regs/_127_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai32_1 \u_regs/_368_  (.A1(\u_regs/_123_ ),
    .A2(\u_regs/_124_ ),
    .A3(\u_regs/_125_ ),
    .B1(\u_regs/_127_ ),
    .B2(\u_regs/cmd [2]),
    .ZN(\u_regs/_128_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_369_  (.A1(\u_regs/cmd [7]),
    .A2(\u_regs/_084_ ),
    .Z(\u_regs/_129_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai211_1 \u_regs/_370_  (.A1(\u_regs/arm ),
    .A2(\u_regs/_105_ ),
    .B(\u_regs/_103_ ),
    .C(\u_regs/_101_ ),
    .ZN(\u_regs/_130_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_371_  (.A1(\u_regs/_129_ ),
    .A2(\u_regs/_130_ ),
    .Z(\u_regs/_131_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_372_  (.A1(\u_regs/_109_ ),
    .A2(\u_regs/_121_ ),
    .A3(\u_regs/_128_ ),
    .A4(\u_regs/_131_ ),
    .ZN(\u_regs/_132_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_373_  (.A1(\u_regs/arm_cnt [3]),
    .A2(\u_regs/arm_cnt [4]),
    .ZN(\u_regs/_133_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_374_  (.A1(\u_regs/arm_cnt [1]),
    .A2(\u_regs/arm_cnt [2]),
    .ZN(\u_regs/_134_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_375_  (.A1(\u_regs/arm_cnt [5]),
    .A2(\u_regs/arm_cnt [6]),
    .ZN(\u_regs/_135_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_376_  (.A1(\u_regs/_133_ ),
    .A2(\u_regs/_134_ ),
    .A3(\u_regs/_135_ ),
    .ZN(\u_regs/_136_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_377_  (.I(\u_regs/arm_cnt [7]),
    .ZN(\u_regs/_137_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_378_  (.A1(\u_regs/arm_cnt [10]),
    .A2(\u_regs/arm_cnt [11]),
    .A3(\u_regs/arm_cnt [12]),
    .ZN(\u_regs/_138_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_379_  (.A1(\u_regs/arm_cnt [8]),
    .A2(\u_regs/arm_cnt [9]),
    .ZN(\u_regs/_139_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_4 \u_regs/_380_  (.A1(\u_regs/arm_cnt [0]),
    .A2(\u_regs/_137_ ),
    .A3(\u_regs/_138_ ),
    .A4(\u_regs/_139_ ),
    .ZN(\u_regs/_140_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_4 \u_regs/_381_  (.A1(prog_en),
    .A2(\u_regs/_085_ ),
    .ZN(\u_regs/_141_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_382_  (.A1(\u_regs/_136_ ),
    .A2(\u_regs/_140_ ),
    .B(\u_regs/_141_ ),
    .ZN(\u_regs/_142_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi211_1 \u_regs/_383_  (.A1(\u_regs/_099_ ),
    .A2(\u_regs/_132_ ),
    .B(\u_regs/_142_ ),
    .C(\u_regs/_123_ ),
    .ZN(\u_regs/_143_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_2 \u_regs/_384_  (.A1(\u_regs/_094_ ),
    .A2(\u_regs/_129_ ),
    .Z(\u_regs/_144_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_385_  (.A1(\u_regs/_120_ ),
    .A2(\u_regs/_144_ ),
    .ZN(\u_regs/_145_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_386_  (.A1(\u_regs/_110_ ),
    .A2(\u_regs/_106_ ),
    .Z(\u_regs/_146_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai22_1 \u_regs/_387_  (.A1(\u_regs/_091_ ),
    .A2(\u_regs/_143_ ),
    .B1(\u_regs/_145_ ),
    .B2(\u_regs/_146_ ),
    .ZN(\u_regs/_147_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_388_  (.A1(\u_regs/_124_ ),
    .A2(\u_regs/_125_ ),
    .ZN(\u_regs/_148_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_389_  (.A1(\u_regs/_148_ ),
    .A2(\u_regs/_144_ ),
    .Z(\u_regs/_149_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_2 \u_regs/_391_  (.A1(\u_regs/arm ),
    .A2(\u_regs/_110_ ),
    .A3(\u_regs/_112_ ),
    .A4(\u_regs/_145_ ),
    .ZN(\u_regs/_151_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_392_  (.A1(\u_regs/_149_ ),
    .A2(\u_regs/_151_ ),
    .ZN(\u_regs/_152_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_393_  (.A1(\u_regs/_147_ ),
    .A2(\u_regs/_152_ ),
    .ZN(\u_regs/_000_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_394_  (.A1(\u_regs/_148_ ),
    .A2(\u_regs/_144_ ),
    .ZN(\u_regs/_153_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_395_  (.A1(\u_regs/_090_ ),
    .A2(\u_regs/_153_ ),
    .ZN(\u_regs/_002_ ));
 gf180mcu_fd_sc_mcu7t5v0__or4_1 \u_regs/_396_  (.A1(\u_regs/rd_cnt [1]),
    .A2(\u_regs/rd_cnt [2]),
    .A3(\u_regs/rd_cnt [3]),
    .A4(\u_regs/rd_cnt [5]),
    .Z(\u_regs/_154_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_397_  (.I(\u_regs/rd_cnt [7]),
    .ZN(\u_regs/_155_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_398_  (.A1(\u_regs/rd_cnt [0]),
    .A2(\u_regs/_155_ ),
    .ZN(\u_regs/_156_ ));
 gf180mcu_fd_sc_mcu7t5v0__or4_1 \u_regs/_399_  (.A1(\u_regs/rd_cnt [4]),
    .A2(\u_regs/rd_cnt [6]),
    .A3(\u_regs/_154_ ),
    .A4(\u_regs/_156_ ),
    .Z(\u_regs/_157_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_4 \u_regs/_400_  (.A1(\u_regs/arm ),
    .A2(\u_regs/_110_ ),
    .A3(\u_regs/_114_ ),
    .A4(\u_regs/_145_ ),
    .ZN(\u_regs/_158_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_401_  (.A1(read_en),
    .A2(\u_regs/_157_ ),
    .B(\u_regs/_158_ ),
    .ZN(\u_regs/_159_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_402_  (.I(\u_regs/_159_ ),
    .ZN(\u_regs/_001_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_403_  (.I(\u_regs/miso_r ),
    .ZN(\u_regs/_160_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_404_  (.A1(\u_regs/cs_2 ),
    .A2(\u_regs/_160_ ),
    .ZN(miso));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_406_  (.I(\u_regs/arm_cnt [2]),
    .ZN(\u_regs/_162_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_407_  (.I(\u_regs/arm_cnt [0]),
    .ZN(\u_regs/_163_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai211_4 \u_regs/_408_  (.A1(\u_regs/_136_ ),
    .A2(\u_regs/_140_ ),
    .B(\u_regs/_163_ ),
    .C(\u_regs/_141_ ),
    .ZN(\u_regs/_164_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_409_  (.A1(\u_regs/arm_cnt [1]),
    .A2(\u_regs/_164_ ),
    .ZN(\u_regs/_165_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_410_  (.A1(\u_regs/_162_ ),
    .A2(\u_regs/_165_ ),
    .ZN(\u_regs/_166_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_411_  (.A1(\u_regs/arm_cnt [3]),
    .A2(\u_regs/_166_ ),
    .Z(\u_regs/_167_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_412_  (.A1(\u_regs/arm_cnt [4]),
    .A2(\u_regs/_167_ ),
    .Z(\u_regs/_168_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_413_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_168_ ),
    .ZN(\u_regs/_003_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_414_  (.I(\u_regs/read_valid ),
    .ZN(\u_regs/_169_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_415_  (.I(read_en),
    .ZN(\u_regs/_170_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_416_  (.A1(\u_regs/_170_ ),
    .A2(\u_regs/_157_ ),
    .Z(\u_regs/_171_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_417_  (.A1(\u_regs/_169_ ),
    .A2(\u_regs/_158_ ),
    .B(\u_regs/_171_ ),
    .ZN(\u_regs/_004_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_418_  (.A1(\u_regs/arm_cnt [3]),
    .A2(\u_regs/_166_ ),
    .ZN(\u_regs/_172_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_419_  (.A1(\u_regs/_167_ ),
    .A2(\u_regs/_172_ ),
    .B(\u_regs/_151_ ),
    .ZN(\u_regs/_005_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_420_  (.A1(\u_regs/arm_cnt [1]),
    .A2(\u_regs/_164_ ),
    .B(\u_regs/arm_cnt [2]),
    .ZN(\u_regs/_173_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_421_  (.A1(\u_regs/_166_ ),
    .A2(\u_regs/_173_ ),
    .B(\u_regs/_151_ ),
    .ZN(\u_regs/_006_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_422_  (.A1(\u_regs/arm_cnt [1]),
    .A2(\u_regs/_164_ ),
    .Z(\u_regs/_174_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_423_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_174_ ),
    .ZN(\u_regs/_007_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_424_  (.A1(\u_regs/arm_cnt [0]),
    .A2(\u_regs/_142_ ),
    .ZN(\u_regs/_175_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_425_  (.A1(\u_regs/_164_ ),
    .A2(\u_regs/_175_ ),
    .B(\u_regs/_151_ ),
    .ZN(\u_regs/_008_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_426_  (.I(\u_regs/bitcnt [4]),
    .ZN(\u_regs/_176_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_427_  (.I(\u_regs/sck_2 ),
    .ZN(\u_regs/_177_ ));
 gf180mcu_fd_sc_mcu7t5v0__or3_1 \u_regs/_428_  (.A1(\u_regs/cs_2 ),
    .A2(\u_regs/sck_d ),
    .A3(\u_regs/_177_ ),
    .Z(\u_regs/_178_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_429_  (.A1(\u_regs/cs_d ),
    .A2(\u_regs/_178_ ),
    .ZN(\u_regs/_179_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_430_  (.A1(\u_regs/bitcnt [3]),
    .A2(\u_regs/_176_ ),
    .A3(\u_regs/_179_ ),
    .ZN(\u_regs/_180_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_431_  (.I0(\u_regs/mosi_2 ),
    .I1(\u_regs/dat [0]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_009_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_432_  (.A1(\u_regs/rd_cnt [0]),
    .A2(\u_regs/_170_ ),
    .Z(\u_regs/_181_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_2 \u_regs/_433_  (.A1(\u_regs/rd_cnt [1]),
    .A2(\u_regs/_181_ ),
    .Z(\u_regs/_182_ ));
 gf180mcu_fd_sc_mcu7t5v0__or3_2 \u_regs/_434_  (.A1(\u_regs/rd_cnt [2]),
    .A2(\u_regs/rd_cnt [3]),
    .A3(\u_regs/_182_ ),
    .Z(\u_regs/_183_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_435_  (.A1(\u_regs/rd_cnt [4]),
    .A2(\u_regs/rd_cnt [5]),
    .A3(\u_regs/rd_cnt [6]),
    .A4(\u_regs/_183_ ),
    .ZN(\u_regs/_184_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_436_  (.A1(\u_regs/_155_ ),
    .A2(\u_regs/_184_ ),
    .Z(\u_regs/_185_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_437_  (.A1(\u_regs/_158_ ),
    .A2(\u_regs/_185_ ),
    .ZN(\u_regs/_010_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_438_  (.A1(miso_oe),
    .A2(\u_regs/cs_d ),
    .ZN(\u_regs/_186_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_439_  (.A1(\u_regs/_122_ ),
    .A2(\u_regs/_186_ ),
    .ZN(\u_regs/_187_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_440_  (.A1(\u_regs/bitcnt [3]),
    .A2(\u_regs/bitcnt [2]),
    .A3(\u_regs/_176_ ),
    .ZN(\u_regs/_188_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_441_  (.I(\u_regs/bitcnt [0]),
    .ZN(\u_regs/_189_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_442_  (.A1(\u_regs/bitcnt [1]),
    .A2(\u_regs/_189_ ),
    .ZN(\u_regs/_190_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_443_  (.A1(\u_regs/_188_ ),
    .A2(\u_regs/_190_ ),
    .B(\u_regs/_178_ ),
    .ZN(\u_regs/_191_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_444_  (.A1(\u_regs/bitcnt [0]),
    .A2(\u_regs/_191_ ),
    .ZN(\u_regs/_192_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_445_  (.A1(\u_regs/bitcnt [1]),
    .A2(\u_regs/_192_ ),
    .Z(\u_regs/_193_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_446_  (.A1(\u_regs/_187_ ),
    .A2(\u_regs/_193_ ),
    .ZN(\u_regs/_011_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_447_  (.I(\u_regs/_144_ ),
    .ZN(\u_regs/_194_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_2 \u_regs/_448_  (.A1(\u_regs/_105_ ),
    .A2(\u_regs/_194_ ),
    .Z(\u_regs/_195_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_4 \u_regs/_449_  (.A1(\u_regs/_118_ ),
    .A2(\u_regs/_104_ ),
    .A3(\u_regs/_195_ ),
    .ZN(\u_regs/_196_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_450_  (.I0(col_sel[4]),
    .I1(\u_regs/dat [4]),
    .S(\u_regs/_196_ ),
    .Z(\u_regs/_012_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_451_  (.A1(\u_regs/cmd [0]),
    .A2(\u_regs/_103_ ),
    .ZN(\u_regs/_197_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_452_  (.A1(\u_regs/mosi_2 ),
    .A2(\u_regs/_095_ ),
    .ZN(\u_regs/_198_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_453_  (.A1(\u_regs/_197_ ),
    .A2(\u_regs/_198_ ),
    .ZN(\u_regs/_199_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_454_  (.A1(\u_regs/pw_r [6]),
    .A2(\u_regs/_199_ ),
    .ZN(\u_regs/_200_ ));
 gf180mcu_fd_sc_mcu7t5v0__and3_1 \u_regs/_455_  (.A1(\u_regs/bitcnt [2]),
    .A2(\u_regs/bitcnt [1]),
    .A3(\u_regs/bitcnt [0]),
    .Z(\u_regs/_201_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_456_  (.I(\u_regs/bitcnt [3]),
    .ZN(\u_regs/_202_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_457_  (.A1(\u_regs/_202_ ),
    .A2(\u_regs/_176_ ),
    .A3(\u_regs/_179_ ),
    .ZN(\u_regs/_203_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_458_  (.I(\u_regs/_203_ ),
    .ZN(\u_regs/_204_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_459_  (.A1(\u_regs/_126_ ),
    .A2(\u_regs/_201_ ),
    .A3(\u_regs/_204_ ),
    .ZN(\u_regs/_205_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_460_  (.A1(\u_regs/_201_ ),
    .A2(\u_regs/_204_ ),
    .ZN(\u_regs/_206_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_461_  (.A1(\u_regs/rd_byte [6]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_207_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_462_  (.A1(\u_regs/_200_ ),
    .A2(\u_regs/_205_ ),
    .B(\u_regs/_207_ ),
    .ZN(\u_regs/_013_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_463_  (.A1(\u_regs/pw_r [5]),
    .A2(\u_regs/_199_ ),
    .ZN(\u_regs/_208_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_464_  (.A1(\u_regs/rd_byte [5]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_209_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_465_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_208_ ),
    .B(\u_regs/_209_ ),
    .ZN(\u_regs/_014_ ));
 gf180mcu_fd_sc_mcu7t5v0__or3_1 \u_regs/_466_  (.A1(\u_regs/cmd [4]),
    .A2(\u_regs/cmd [5]),
    .A3(\u_regs/cmd [3]),
    .Z(\u_regs/_210_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_467_  (.A1(\u_regs/_118_ ),
    .A2(\u_regs/_103_ ),
    .ZN(\u_regs/_211_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_468_  (.A1(\u_regs/mosi_2 ),
    .A2(\u_regs/_210_ ),
    .A3(\u_regs/_211_ ),
    .ZN(\u_regs/_212_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_469_  (.A1(\u_regs/_198_ ),
    .A2(\u_regs/_211_ ),
    .ZN(\u_regs/_213_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi222_1 \u_regs/_470_  (.A1(\u_regs/pw_r [4]),
    .A2(\u_regs/_199_ ),
    .B1(\u_regs/_212_ ),
    .B2(row_sel[4]),
    .C1(\u_regs/_213_ ),
    .C2(col_sel[4]),
    .ZN(\u_regs/_214_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_471_  (.A1(\u_regs/rd_byte [4]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_215_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_472_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_214_ ),
    .B(\u_regs/_215_ ),
    .ZN(\u_regs/_015_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_473_  (.I(\u_regs/_119_ ),
    .ZN(\u_regs/_216_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_474_  (.A1(\u_regs/mosi_2 ),
    .A2(\u_regs/_210_ ),
    .A3(\u_regs/_216_ ),
    .ZN(\u_regs/_217_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_475_  (.A1(col_sel[3]),
    .A2(\u_regs/_213_ ),
    .B1(\u_regs/_217_ ),
    .B2(\u_regs/perr ),
    .ZN(\u_regs/_218_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_476_  (.A1(\u_regs/pw_r [3]),
    .A2(\u_regs/_199_ ),
    .B1(\u_regs/_212_ ),
    .B2(row_sel[3]),
    .ZN(\u_regs/_219_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_477_  (.A1(\u_regs/_218_ ),
    .A2(\u_regs/_219_ ),
    .Z(\u_regs/_220_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_478_  (.A1(\u_regs/rd_byte [3]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_221_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_479_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_220_ ),
    .B(\u_regs/_221_ ),
    .ZN(\u_regs/_016_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_480_  (.A1(\u_regs/pw_r [2]),
    .A2(\u_regs/_199_ ),
    .B1(\u_regs/_217_ ),
    .B2(\u_regs/read_valid ),
    .ZN(\u_regs/_222_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_481_  (.A1(\u_regs/mosi_2 ),
    .A2(\u_regs/_210_ ),
    .A3(\u_regs/_197_ ),
    .ZN(\u_regs/_223_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi222_1 \u_regs/_482_  (.A1(row_sel[2]),
    .A2(\u_regs/_212_ ),
    .B1(\u_regs/_213_ ),
    .B2(col_sel[2]),
    .C1(read_en),
    .C2(\u_regs/_223_ ),
    .ZN(\u_regs/_224_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_483_  (.A1(\u_regs/_222_ ),
    .A2(\u_regs/_224_ ),
    .Z(\u_regs/_225_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_484_  (.A1(\u_regs/rd_byte [2]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_226_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_485_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_225_ ),
    .B(\u_regs/_226_ ),
    .ZN(\u_regs/_017_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_486_  (.A1(row_sel[1]),
    .A2(\u_regs/_212_ ),
    .B1(\u_regs/_223_ ),
    .B2(prog_en),
    .ZN(\u_regs/_227_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi222_1 \u_regs/_487_  (.A1(\u_regs/pw_r [1]),
    .A2(\u_regs/_199_ ),
    .B1(\u_regs/_213_ ),
    .B2(col_sel[1]),
    .C1(\u_regs/_217_ ),
    .C2(\u_regs/prog_done ),
    .ZN(\u_regs/_228_ ));
 gf180mcu_fd_sc_mcu7t5v0__and2_1 \u_regs/_488_  (.A1(\u_regs/_227_ ),
    .A2(\u_regs/_228_ ),
    .Z(\u_regs/_229_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_489_  (.A1(\u_regs/rd_byte [1]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_230_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_490_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_229_ ),
    .B(\u_regs/_230_ ),
    .ZN(\u_regs/_018_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_491_  (.A1(\u_regs/arm ),
    .A2(\u_regs/_223_ ),
    .ZN(\u_regs/_231_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_492_  (.A1(\u_regs/mosi_2 ),
    .A2(\u_regs/rdata ),
    .A3(\u_regs/_095_ ),
    .A4(\u_regs/_119_ ),
    .ZN(\u_regs/_232_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi222_1 \u_regs/_493_  (.A1(\u_regs/pw_r [0]),
    .A2(\u_regs/_199_ ),
    .B1(\u_regs/_213_ ),
    .B2(col_sel[0]),
    .C1(\u_regs/_217_ ),
    .C2(busy),
    .ZN(\u_regs/_233_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_494_  (.A1(\u_regs/_231_ ),
    .A2(\u_regs/_232_ ),
    .A3(\u_regs/_233_ ),
    .ZN(\u_regs/_234_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_495_  (.A1(row_sel[0]),
    .A2(\u_regs/_212_ ),
    .B(\u_regs/_234_ ),
    .ZN(\u_regs/_235_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_496_  (.A1(\u_regs/rd_byte [0]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_236_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_497_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_235_ ),
    .B(\u_regs/_236_ ),
    .ZN(\u_regs/_019_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_498_  (.I(\u_regs/_187_ ),
    .ZN(\u_regs/_237_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_499_  (.A1(\u_regs/_189_ ),
    .A2(\u_regs/_178_ ),
    .ZN(\u_regs/_238_ ));
 gf180mcu_fd_sc_mcu7t5v0__and3_1 \u_regs/_500_  (.A1(\u_regs/_192_ ),
    .A2(\u_regs/_237_ ),
    .A3(\u_regs/_238_ ),
    .Z(\u_regs/_020_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_501_  (.A1(prog_en),
    .A2(\u_regs/_149_ ),
    .ZN(\u_regs/_239_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_502_  (.A1(\u_regs/pw_cnt [0]),
    .A2(\u_regs/pw_cnt [1]),
    .A3(\u_regs/pw_cnt [2]),
    .ZN(\u_regs/_240_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_503_  (.A1(\u_regs/_088_ ),
    .A2(\u_regs/_240_ ),
    .ZN(\u_regs/_241_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_504_  (.A1(\u_regs/pw_cnt [5]),
    .A2(\u_regs/pw_cnt [6]),
    .A3(\u_regs/_241_ ),
    .ZN(\u_regs/_242_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_505_  (.A1(\u_regs/_149_ ),
    .A2(\u_regs/_242_ ),
    .ZN(\u_regs/_243_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_506_  (.A1(\u_regs/_239_ ),
    .A2(\u_regs/_243_ ),
    .ZN(\u_regs/_244_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_507_  (.A1(\u_regs/pw_cnt [5]),
    .A2(\u_regs/_241_ ),
    .ZN(\u_regs/_245_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_508_  (.A1(prog_en),
    .A2(\u_regs/pw_cnt [6]),
    .A3(\u_regs/_153_ ),
    .A4(\u_regs/_245_ ),
    .ZN(\u_regs/_246_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai221_1 \u_regs/_509_  (.A1(\u_regs/pw_r [6]),
    .A2(\u_regs/_153_ ),
    .B1(\u_regs/_244_ ),
    .B2(\u_regs/pw_cnt [6]),
    .C(\u_regs/_246_ ),
    .ZN(\u_regs/_247_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_510_  (.I(\u_regs/_247_ ),
    .ZN(\u_regs/_021_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_regs/_511_  (.A1(\u_regs/_127_ ),
    .A2(\u_regs/_195_ ),
    .A3(\u_regs/_211_ ),
    .ZN(\u_regs/_248_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_512_  (.I0(row_sel[4]),
    .I1(\u_regs/dat [4]),
    .S(\u_regs/_248_ ),
    .Z(\u_regs/_022_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_513_  (.A1(\u_regs/_099_ ),
    .A2(\u_regs/_132_ ),
    .B(\u_regs/_123_ ),
    .ZN(\u_regs/_249_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_514_  (.A1(\u_regs/cmd [1]),
    .A2(\u_regs/cmd [0]),
    .A3(\u_regs/_210_ ),
    .ZN(\u_regs/_250_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand4_1 \u_regs/_515_  (.A1(\u_regs/cmd [2]),
    .A2(\u_regs/_094_ ),
    .A3(\u_regs/_096_ ),
    .A4(\u_regs/_250_ ),
    .ZN(\u_regs/_251_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_516_  (.A1(\u_regs/perr ),
    .A2(\u_regs/_251_ ),
    .ZN(\u_regs/_252_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_517_  (.A1(\u_regs/_249_ ),
    .A2(\u_regs/_252_ ),
    .ZN(\u_regs/_023_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_518_  (.I0(row_sel[3]),
    .I1(\u_regs/dat [3]),
    .S(\u_regs/_248_ ),
    .Z(\u_regs/_024_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_519_  (.I0(row_sel[2]),
    .I1(\u_regs/dat [2]),
    .S(\u_regs/_248_ ),
    .Z(\u_regs/_025_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_520_  (.I0(row_sel[1]),
    .I1(\u_regs/dat [1]),
    .S(\u_regs/_248_ ),
    .Z(\u_regs/_026_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_521_  (.A1(\u_regs/pw_r [7]),
    .A2(\u_regs/_199_ ),
    .ZN(\u_regs/_253_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_522_  (.A1(\u_regs/rd_byte [7]),
    .A2(\u_regs/_206_ ),
    .ZN(\u_regs/_254_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_523_  (.A1(\u_regs/_205_ ),
    .A2(\u_regs/_253_ ),
    .B(\u_regs/_254_ ),
    .ZN(\u_regs/_027_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_524_  (.I0(row_sel[0]),
    .I1(\u_regs/dat [0]),
    .S(\u_regs/_248_ ),
    .Z(\u_regs/_028_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_525_  (.I0(col_sel[3]),
    .I1(\u_regs/dat [3]),
    .S(\u_regs/_196_ ),
    .Z(\u_regs/_029_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_526_  (.I0(col_sel[2]),
    .I1(\u_regs/dat [2]),
    .S(\u_regs/_196_ ),
    .Z(\u_regs/_030_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_527_  (.A1(\u_regs/arm ),
    .A2(\u_regs/_110_ ),
    .A3(\u_regs/_112_ ),
    .A4(\u_regs/_145_ ),
    .ZN(\u_regs/_255_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_528_  (.A1(\u_regs/_133_ ),
    .A2(\u_regs/_135_ ),
    .ZN(\u_regs/_256_ ));
 gf180mcu_fd_sc_mcu7t5v0__or4_4 \u_regs/_529_  (.A1(\u_regs/arm_cnt [1]),
    .A2(\u_regs/arm_cnt [2]),
    .A3(\u_regs/_164_ ),
    .A4(\u_regs/_256_ ),
    .Z(\u_regs/_257_ ));
 gf180mcu_fd_sc_mcu7t5v0__or4_4 \u_regs/_530_  (.A1(\u_regs/arm_cnt [7]),
    .A2(\u_regs/arm_cnt [8]),
    .A3(\u_regs/arm_cnt [9]),
    .A4(\u_regs/_257_ ),
    .Z(\u_regs/_258_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_4 \u_regs/_531_  (.A1(\u_regs/arm_cnt [10]),
    .A2(\u_regs/arm_cnt [11]),
    .A3(\u_regs/_258_ ),
    .ZN(\u_regs/_259_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_2 \u_regs/_532_  (.A1(\u_regs/arm_cnt [12]),
    .A2(\u_regs/_259_ ),
    .Z(\u_regs/_260_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_2 \u_regs/_533_  (.A1(\u_regs/_255_ ),
    .A2(\u_regs/_260_ ),
    .Z(\u_regs/_031_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_534_  (.I0(\u_regs/cmd [6]),
    .I1(\u_regs/cmd [7]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_032_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_535_  (.I0(col_sel[1]),
    .I1(\u_regs/dat [1]),
    .S(\u_regs/_196_ ),
    .Z(\u_regs/_033_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_536_  (.I0(col_sel[0]),
    .I1(\u_regs/dat [0]),
    .S(\u_regs/_196_ ),
    .Z(\u_regs/_034_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_537_  (.A1(\u_regs/rd_cnt [4]),
    .A2(\u_regs/_154_ ),
    .A3(\u_regs/_181_ ),
    .ZN(\u_regs/_261_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_538_  (.A1(\u_regs/rd_cnt [6]),
    .A2(\u_regs/_261_ ),
    .ZN(\u_regs/_262_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_539_  (.A1(\u_regs/_158_ ),
    .A2(\u_regs/_262_ ),
    .ZN(\u_regs/_035_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_540_  (.A1(\u_regs/rd_cnt [4]),
    .A2(\u_regs/_183_ ),
    .ZN(\u_regs/_263_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_541_  (.A1(\u_regs/rd_cnt [5]),
    .A2(\u_regs/_263_ ),
    .ZN(\u_regs/_264_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_542_  (.A1(\u_regs/_158_ ),
    .A2(\u_regs/_264_ ),
    .ZN(\u_regs/_036_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_543_  (.A1(\u_regs/rd_cnt [4]),
    .A2(\u_regs/_183_ ),
    .Z(\u_regs/_265_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_544_  (.A1(\u_regs/_158_ ),
    .A2(\u_regs/_265_ ),
    .ZN(\u_regs/_037_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_545_  (.A1(\u_regs/rd_cnt [2]),
    .A2(\u_regs/_182_ ),
    .B(\u_regs/rd_cnt [3]),
    .ZN(\u_regs/_266_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_546_  (.A1(\u_regs/_183_ ),
    .A2(\u_regs/_266_ ),
    .ZN(\u_regs/_267_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_547_  (.A1(\u_regs/_158_ ),
    .A2(\u_regs/_267_ ),
    .Z(\u_regs/_038_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_548_  (.A1(\u_regs/rd_cnt [2]),
    .A2(\u_regs/_182_ ),
    .Z(\u_regs/_268_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_549_  (.A1(\u_regs/_158_ ),
    .A2(\u_regs/_268_ ),
    .ZN(\u_regs/_039_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_550_  (.A1(\u_regs/rd_cnt [1]),
    .A2(\u_regs/_181_ ),
    .ZN(\u_regs/_269_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_551_  (.A1(\u_regs/_182_ ),
    .A2(\u_regs/_269_ ),
    .B(\u_regs/_158_ ),
    .ZN(\u_regs/_040_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_552_  (.A1(\u_regs/rd_cnt [0]),
    .A2(\u_regs/_170_ ),
    .ZN(\u_regs/_270_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_553_  (.A1(\u_regs/_181_ ),
    .A2(\u_regs/_270_ ),
    .B(\u_regs/_158_ ),
    .ZN(\u_regs/_041_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_554_  (.I(prog_en),
    .ZN(\u_regs/_271_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai211_1 \u_regs/_555_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/_241_ ),
    .B(\u_regs/_153_ ),
    .C(\u_regs/pw_cnt [5]),
    .ZN(\u_regs/_272_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_556_  (.A1(\u_regs/pw_r [5]),
    .A2(\u_regs/_149_ ),
    .B1(\u_regs/_245_ ),
    .B2(prog_en),
    .ZN(\u_regs/_273_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_557_  (.A1(\u_regs/_272_ ),
    .A2(\u_regs/_273_ ),
    .ZN(\u_regs/_042_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor4_1 \u_regs/_558_  (.A1(\u_regs/pw_cnt [0]),
    .A2(\u_regs/pw_cnt [1]),
    .A3(\u_regs/pw_cnt [2]),
    .A4(\u_regs/pw_cnt [3]),
    .ZN(\u_regs/_274_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_559_  (.A1(\u_regs/pw_cnt [4]),
    .A2(\u_regs/_274_ ),
    .ZN(\u_regs/_275_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_560_  (.A1(\u_regs/pw_r [4]),
    .A2(\u_regs/_149_ ),
    .B1(\u_regs/_239_ ),
    .B2(\u_regs/pw_cnt [4]),
    .ZN(\u_regs/_276_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_561_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/_275_ ),
    .B(\u_regs/_276_ ),
    .ZN(\u_regs/_043_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_562_  (.A1(\u_regs/pw_cnt [3]),
    .A2(\u_regs/_240_ ),
    .ZN(\u_regs/_277_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_563_  (.A1(\u_regs/pw_r [3]),
    .A2(\u_regs/_149_ ),
    .B1(\u_regs/_239_ ),
    .B2(\u_regs/pw_cnt [3]),
    .ZN(\u_regs/_278_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_564_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/_277_ ),
    .B(\u_regs/_278_ ),
    .ZN(\u_regs/_044_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_565_  (.A1(\u_regs/pw_cnt [0]),
    .A2(\u_regs/pw_cnt [1]),
    .ZN(\u_regs/_279_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_566_  (.A1(\u_regs/pw_cnt [2]),
    .A2(\u_regs/_279_ ),
    .ZN(\u_regs/_280_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_567_  (.A1(\u_regs/pw_r [2]),
    .A2(\u_regs/_149_ ),
    .B1(\u_regs/_239_ ),
    .B2(\u_regs/pw_cnt [2]),
    .ZN(\u_regs/_281_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_568_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/_280_ ),
    .B(\u_regs/_281_ ),
    .ZN(\u_regs/_045_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_569_  (.A1(\u_regs/pw_cnt [0]),
    .A2(\u_regs/pw_cnt [1]),
    .Z(\u_regs/_282_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_570_  (.A1(\u_regs/pw_r [1]),
    .A2(\u_regs/_149_ ),
    .B1(\u_regs/_239_ ),
    .B2(\u_regs/pw_cnt [1]),
    .ZN(\u_regs/_283_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_571_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/_282_ ),
    .B(\u_regs/_283_ ),
    .ZN(\u_regs/_046_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_572_  (.A1(\u_regs/pw_r [0]),
    .A2(\u_regs/_149_ ),
    .ZN(\u_regs/_284_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_573_  (.A1(\u_regs/pw_cnt [0]),
    .A2(\u_regs/_239_ ),
    .ZN(\u_regs/_285_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai211_1 \u_regs/_574_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/pw_cnt [0]),
    .B(\u_regs/_284_ ),
    .C(\u_regs/_285_ ),
    .ZN(\u_regs/_047_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_575_  (.A1(\u_regs/_102_ ),
    .A2(\u_regs/_194_ ),
    .ZN(\u_regs/_286_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_regs/_576_  (.A1(\u_regs/_146_ ),
    .A2(\u_regs/_286_ ),
    .ZN(\u_regs/_287_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_577_  (.I0(\u_regs/dat [6]),
    .I1(\u_regs/pw_r [6]),
    .S(\u_regs/_287_ ),
    .Z(\u_regs/_048_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_578_  (.I0(\u_regs/dat [5]),
    .I1(\u_regs/pw_r [5]),
    .S(\u_regs/_287_ ),
    .Z(\u_regs/_049_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_579_  (.I0(\u_regs/sns_2 ),
    .I1(\u_regs/rdata ),
    .S(\u_regs/_171_ ),
    .Z(\u_regs/_050_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_580_  (.I0(\u_regs/dat [4]),
    .I1(\u_regs/pw_r [4]),
    .S(\u_regs/_287_ ),
    .Z(\u_regs/_051_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_581_  (.I0(\u_regs/dat [7]),
    .I1(\u_regs/pw_r [7]),
    .S(\u_regs/_287_ ),
    .Z(\u_regs/_052_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_582_  (.A1(\u_regs/dat [3]),
    .A2(\u_regs/_286_ ),
    .B1(\u_regs/_287_ ),
    .B2(\u_regs/pw_r [3]),
    .ZN(\u_regs/_288_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_583_  (.I(\u_regs/_288_ ),
    .ZN(\u_regs/_053_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi22_1 \u_regs/_584_  (.A1(\u_regs/dat [2]),
    .A2(\u_regs/_286_ ),
    .B1(\u_regs/_287_ ),
    .B2(\u_regs/pw_r [2]),
    .ZN(\u_regs/_289_ ));
 gf180mcu_fd_sc_mcu7t5v0__inv_1 \u_regs/_585_  (.I(\u_regs/_289_ ),
    .ZN(\u_regs/_054_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_586_  (.I0(\u_regs/dat [1]),
    .I1(\u_regs/pw_r [1]),
    .S(\u_regs/_287_ ),
    .Z(\u_regs/_055_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai22_1 \u_regs/_587_  (.A1(\u_regs/pw_r [7]),
    .A2(\u_regs/_153_ ),
    .B1(\u_regs/_244_ ),
    .B2(\u_regs/pw_cnt [7]),
    .ZN(\u_regs/_290_ ));
 gf180mcu_fd_sc_mcu7t5v0__and3_1 \u_regs/_588_  (.A1(prog_en),
    .A2(\u_regs/pw_cnt [7]),
    .A3(\u_regs/_242_ ),
    .Z(\u_regs/_291_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_589_  (.A1(\u_regs/_290_ ),
    .A2(\u_regs/_291_ ),
    .ZN(\u_regs/_056_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_590_  (.I0(\u_regs/dat [0]),
    .I1(\u_regs/pw_r [0]),
    .S(\u_regs/_287_ ),
    .Z(\u_regs/_057_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_591_  (.A1(\u_regs/_191_ ),
    .A2(\u_regs/_187_ ),
    .B(\u_regs/_201_ ),
    .ZN(\u_regs/_292_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_592_  (.A1(\u_regs/cs_2 ),
    .A2(\u_regs/sck_d ),
    .A3(\u_regs/_177_ ),
    .ZN(\u_regs/_293_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_593_  (.A1(\u_regs/bitcnt [3]),
    .A2(\u_regs/_293_ ),
    .A3(\u_regs/_201_ ),
    .ZN(\u_regs/_294_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_594_  (.A1(\u_regs/_237_ ),
    .A2(\u_regs/_294_ ),
    .ZN(\u_regs/_295_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_595_  (.A1(\u_regs/_202_ ),
    .A2(\u_regs/_292_ ),
    .B(\u_regs/_295_ ),
    .ZN(\u_regs/_058_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai211_1 \u_regs/_596_  (.A1(\u_regs/_293_ ),
    .A2(\u_regs/_187_ ),
    .B(\u_regs/bitcnt [1]),
    .C(\u_regs/bitcnt [0]),
    .ZN(\u_regs/_296_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_597_  (.I(\u_regs/bitcnt [2]),
    .ZN(\u_regs/_297_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi221_1 \u_regs/_598_  (.A1(\u_regs/_191_ ),
    .A2(\u_regs/_201_ ),
    .B1(\u_regs/_296_ ),
    .B2(\u_regs/_297_ ),
    .C(\u_regs/_187_ ),
    .ZN(\u_regs/_059_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_599_  (.I0(\u_regs/dat [6]),
    .I1(\u_regs/dat [7]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_060_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_600_  (.I0(\u_regs/dat [5]),
    .I1(\u_regs/dat [6]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_061_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_601_  (.I0(\u_regs/dat [4]),
    .I1(\u_regs/dat [5]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_062_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_602_  (.I0(\u_regs/dat [3]),
    .I1(\u_regs/dat [4]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_063_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_603_  (.I0(\u_regs/dat [2]),
    .I1(\u_regs/dat [3]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_064_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_604_  (.I0(\u_regs/dat [1]),
    .I1(\u_regs/dat [2]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_065_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_605_  (.I0(\u_regs/cmd [5]),
    .I1(\u_regs/cmd [6]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_066_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_606_  (.A1(\u_regs/bitcnt [3]),
    .A2(\u_regs/_176_ ),
    .ZN(\u_regs/_298_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai32_1 \u_regs/_607_  (.A1(\u_regs/_298_ ),
    .A2(\u_regs/_187_ ),
    .A3(\u_regs/_292_ ),
    .B1(\u_regs/_295_ ),
    .B2(\u_regs/_176_ ),
    .ZN(\u_regs/_067_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_608_  (.I0(\u_regs/cmd [4]),
    .I1(\u_regs/cmd [5]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_068_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_609_  (.I0(\u_regs/cmd [3]),
    .I1(\u_regs/cmd [4]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_069_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_610_  (.I0(\u_regs/cmd [2]),
    .I1(\u_regs/cmd [3]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_070_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_611_  (.I0(\u_regs/cmd [1]),
    .I1(\u_regs/cmd [2]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_071_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_612_  (.I0(\u_regs/cmd [0]),
    .I1(\u_regs/cmd [1]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_072_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_613_  (.I0(\u_regs/mosi_2 ),
    .I1(\u_regs/cmd [0]),
    .S(\u_regs/_203_ ),
    .Z(\u_regs/_073_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_614_  (.I0(\u_regs/dat [0]),
    .I1(\u_regs/dat [1]),
    .S(\u_regs/_180_ ),
    .Z(\u_regs/_074_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_615_  (.A1(\u_regs/arm_cnt [10]),
    .A2(\u_regs/_258_ ),
    .ZN(\u_regs/_299_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_616_  (.A1(\u_regs/arm_cnt [11]),
    .A2(\u_regs/_299_ ),
    .ZN(\u_regs/_300_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_617_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_300_ ),
    .ZN(\u_regs/_075_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_618_  (.A1(\u_regs/arm_cnt [10]),
    .A2(\u_regs/_258_ ),
    .Z(\u_regs/_301_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_619_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_301_ ),
    .ZN(\u_regs/_076_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_regs/_620_  (.A1(\u_regs/arm_cnt [7]),
    .A2(\u_regs/arm_cnt [8]),
    .A3(\u_regs/_257_ ),
    .ZN(\u_regs/_302_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_621_  (.A1(\u_regs/arm_cnt [9]),
    .A2(\u_regs/_302_ ),
    .ZN(\u_regs/_303_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_622_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_303_ ),
    .ZN(\u_regs/_077_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_623_  (.A1(\u_regs/arm_cnt [7]),
    .A2(\u_regs/_257_ ),
    .ZN(\u_regs/_304_ ));
 gf180mcu_fd_sc_mcu7t5v0__xnor2_1 \u_regs/_624_  (.A1(\u_regs/arm_cnt [8]),
    .A2(\u_regs/_304_ ),
    .ZN(\u_regs/_305_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_625_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_305_ ),
    .ZN(\u_regs/_078_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_626_  (.A1(\u_regs/arm_cnt [7]),
    .A2(\u_regs/_257_ ),
    .Z(\u_regs/_306_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_627_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_306_ ),
    .ZN(\u_regs/_079_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_628_  (.A1(\u_regs/_162_ ),
    .A2(\u_regs/_133_ ),
    .A3(\u_regs/_165_ ),
    .ZN(\u_regs/_307_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_629_  (.A1(\u_regs/arm_cnt [5]),
    .A2(\u_regs/_307_ ),
    .B(\u_regs/arm_cnt [6]),
    .ZN(\u_regs/_308_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_630_  (.A1(\u_regs/_257_ ),
    .A2(\u_regs/_308_ ),
    .B(\u_regs/_151_ ),
    .ZN(\u_regs/_080_ ));
 gf180mcu_fd_sc_mcu7t5v0__xor2_1 \u_regs/_631_  (.A1(\u_regs/arm_cnt [5]),
    .A2(\u_regs/_307_ ),
    .Z(\u_regs/_309_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_632_  (.A1(\u_regs/_151_ ),
    .A2(\u_regs/_309_ ),
    .ZN(\u_regs/_081_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_regs/_633_  (.A1(miso_oe),
    .A2(\u_regs/sck_d ),
    .A3(\u_regs/_177_ ),
    .ZN(\u_regs/_310_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_regs/_634_  (.A1(\u_regs/bitcnt [1]),
    .A2(\u_regs/bitcnt [0]),
    .ZN(\u_regs/_311_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_regs/_635_  (.A1(\u_regs/rd_byte [7]),
    .A2(\u_regs/_311_ ),
    .ZN(\u_regs/_312_ ));
 gf180mcu_fd_sc_mcu7t5v0__mux2_1 \u_regs/_636_  (.I0(\u_regs/rd_byte [5]),
    .I1(\u_regs/rd_byte [4]),
    .S(\u_regs/bitcnt [0]),
    .Z(\u_regs/_313_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi221_1 \u_regs/_637_  (.A1(\u_regs/rd_byte [6]),
    .A2(\u_regs/_190_ ),
    .B1(\u_regs/_313_ ),
    .B2(\u_regs/bitcnt [1]),
    .C(\u_regs/bitcnt [2]),
    .ZN(\u_regs/_314_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_1 \u_regs/_638_  (.A1(\u_regs/bitcnt [0]),
    .A2(\u_regs/rd_byte [1]),
    .Z(\u_regs/_315_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai211_1 \u_regs/_639_  (.A1(\u_regs/_189_ ),
    .A2(\u_regs/rd_byte [0]),
    .B(\u_regs/_315_ ),
    .C(\u_regs/bitcnt [1]),
    .ZN(\u_regs/_316_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi221_1 \u_regs/_640_  (.A1(\u_regs/rd_byte [3]),
    .A2(\u_regs/_311_ ),
    .B1(\u_regs/_190_ ),
    .B2(\u_regs/rd_byte [2]),
    .C(\u_regs/_297_ ),
    .ZN(\u_regs/_317_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi221_1 \u_regs/_641_  (.A1(\u_regs/_312_ ),
    .A2(\u_regs/_314_ ),
    .B1(\u_regs/_316_ ),
    .B2(\u_regs/_317_ ),
    .C(\u_regs/_298_ ),
    .ZN(\u_regs/_318_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai21_1 \u_regs/_642_  (.A1(\u_regs/_310_ ),
    .A2(\u_regs/_318_ ),
    .B(\u_regs/_122_ ),
    .ZN(\u_regs/_319_ ));
 gf180mcu_fd_sc_mcu7t5v0__aoi21_1 \u_regs/_643_  (.A1(\u_regs/_160_ ),
    .A2(\u_regs/_310_ ),
    .B(\u_regs/_319_ ),
    .ZN(\u_regs/_082_ ));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_1 \u_regs/_644_  (.I(\u_regs/prog_done ),
    .ZN(\u_regs/_320_ ));
 gf180mcu_fd_sc_mcu7t5v0__oai22_1 \u_regs/_645_  (.A1(\u_regs/_271_ ),
    .A2(\u_regs/_089_ ),
    .B1(\u_regs/_151_ ),
    .B2(\u_regs/_320_ ),
    .ZN(\u_regs/_083_ ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_646_  (.D(\u_regs/_004_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/read_valid ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_647_  (.D(\u_regs/_041_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_648_  (.D(\u_regs/_040_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_649_  (.D(\u_regs/_039_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/rd_cnt [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_650_  (.D(\u_regs/_038_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_651_  (.D(\u_regs/_037_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_652_  (.D(\u_regs/_036_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_653_  (.D(\u_regs/_035_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_654_  (.D(\u_regs/_010_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rd_cnt [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_655_  (.D(\u_regs/_034_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(col_sel[0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_656_  (.D(\u_regs/_033_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(col_sel[1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_657_  (.D(\u_regs/_030_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(col_sel[2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_658_  (.D(\u_regs/_029_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(col_sel[3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_659_  (.D(\u_regs/_012_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(col_sel[4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_660_  (.D(\u_regs/_028_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(row_sel[0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_661_  (.D(\u_regs/_026_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(row_sel[1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_662_  (.D(\u_regs/_025_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(row_sel[2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_663_  (.D(\u_regs/_024_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(row_sel[3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_664_  (.D(\u_regs/_022_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(row_sel[4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_665_  (.D(\u_regs/_023_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/perr ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_666_  (.D(\u_regs/_019_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/rd_byte [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_667_  (.D(\u_regs/_018_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/rd_byte [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_668_  (.D(\u_regs/_017_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/rd_byte [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_669_  (.D(\u_regs/_016_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/rd_byte [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_670_  (.D(\u_regs/_015_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/rd_byte [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_671_  (.D(\u_regs/_014_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/rd_byte [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_672_  (.D(\u_regs/_013_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/rd_byte [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_673_  (.D(\u_regs/_027_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/rd_byte [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_674_  (.D(\u_regs/_008_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_675_  (.D(\u_regs/_007_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/arm_cnt [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_676_  (.D(\u_regs/_006_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/arm_cnt [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_677_  (.D(\u_regs/_005_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/arm_cnt [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_678_  (.D(\u_regs/_003_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/arm_cnt [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_679_  (.D(\u_regs/_081_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/arm_cnt [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_680_  (.D(\u_regs/_080_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_681_  (.D(\u_regs/_079_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_682_  (.D(\u_regs/_078_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [8]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_683_  (.D(\u_regs/_077_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [9]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_684_  (.D(\u_regs/_076_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [10]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_685_  (.D(\u_regs/_075_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm_cnt [11]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_686_  (.D(\u_regs/_031_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/arm_cnt [12]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_687_  (.D(\u_regs/_073_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/cmd [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_688_  (.D(\u_regs/_072_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/cmd [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_689_  (.D(\u_regs/_071_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/cmd [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_690_  (.D(\u_regs/_070_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/cmd [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_691_  (.D(\u_regs/_069_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/cmd [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_692_  (.D(\u_regs/_068_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_0__leaf_clk),
    .Q(\u_regs/cmd [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_693_  (.D(\u_regs/_066_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/cmd [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_694_  (.D(\u_regs/_032_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/cmd [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_695_  (.D(\u_regs/_050_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/rdata ));
 gf180mcu_fd_sc_mcu7t5v0__dffsnq_1 \u_regs/_696_  (.D(\u_regs/_057_ ),
    .SETN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_r [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_697_  (.D(\u_regs/_055_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_r [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_698_  (.D(\u_regs/_054_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_r [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_699_  (.D(\u_regs/_053_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_r [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_700_  (.D(\u_regs/_051_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_r [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_701_  (.D(\u_regs/_049_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_r [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_702_  (.D(\u_regs/_048_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_r [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_703_  (.D(\u_regs/_052_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_r [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_704_  (.D(\u_regs/_047_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_cnt [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_705_  (.D(\u_regs/_046_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_cnt [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_706_  (.D(\u_regs/_045_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_cnt [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_707_  (.D(\u_regs/_044_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_cnt [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_708_  (.D(\u_regs/_043_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/pw_cnt [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_709_  (.D(\u_regs/_042_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_cnt [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_710_  (.D(\u_regs/_021_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_cnt [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_711_  (.D(\u_regs/_056_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/pw_cnt [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_712_  (.D(\u_regs/_009_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/dat [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_713_  (.D(\u_regs/_074_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/dat [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_714_  (.D(\u_regs/_065_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/dat [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_715_  (.D(\u_regs/_064_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/dat [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_716_  (.D(\u_regs/_063_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_6__leaf_clk),
    .Q(\u_regs/dat [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_717_  (.D(\u_regs/_062_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/dat [5]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_718_  (.D(\u_regs/_061_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/dat [6]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_719_  (.D(\u_regs/_060_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(\u_regs/dat [7]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_720_  (.D(\u_regs/_020_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/bitcnt [0]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_721_  (.D(\u_regs/_011_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/bitcnt [1]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_722_  (.D(\u_regs/_059_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/bitcnt [2]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_723_  (.D(\u_regs/_058_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/bitcnt [3]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_724_  (.D(\u_regs/_067_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_1__leaf_clk),
    .Q(\u_regs/bitcnt [4]));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_725_  (.D(\u_regs/_082_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/miso_r ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_726_  (.D(\u_regs/_083_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/prog_done ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_727_  (.D(\u_regs/_000_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_2__leaf_clk),
    .Q(\u_regs/arm ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_728_  (.D(\u_regs/_002_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_3__leaf_clk),
    .Q(prog_en));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_729_  (.D(\u_regs/_001_ ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(read_en));
 gf180mcu_fd_sc_mcu7t5v0__dffsnq_1 \u_regs/_730_  (.D(cs_n),
    .SETN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/cs_1 ));
 gf180mcu_fd_sc_mcu7t5v0__dffsnq_1 \u_regs/_731_  (.D(\u_regs/cs_1 ),
    .SETN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/cs_2 ));
 gf180mcu_fd_sc_mcu7t5v0__dffsnq_1 \u_regs/_732_  (.D(\u_regs/cs_2 ),
    .SETN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/cs_d ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_733_  (.D(sclk),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/sck_1 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_734_  (.D(\u_regs/sck_1 ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/sck_2 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_735_  (.D(\u_regs/sck_2 ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/sck_d ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_736_  (.D(mosi),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/mosi_1 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_737_  (.D(\u_regs/mosi_1 ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_4__leaf_clk),
    .Q(\u_regs/mosi_2 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_738_  (.D(sense_in),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/sns_1 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_739_  (.D(\u_regs/sns_1 ),
    .RN(\u_regs/net3 ),
    .CLK(clknet_3_7__leaf_clk),
    .Q(\u_regs/sns_2 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_1 \u_regs/_740_  (.D(\u_regs/_321_ ),
    .RN(rst_n),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/rs1 ));
 gf180mcu_fd_sc_mcu7t5v0__dffrnq_4 \u_regs/_741_  (.D(\u_regs/rs1 ),
    .RN(rst_n),
    .CLK(clknet_3_5__leaf_clk),
    .Q(\u_regs/rst_s ));
 gf180mcu_fd_sc_mcu7t5v0__tieh \u_regs/_742_  (.Z(\u_regs/_321_ ));
 gf180mcu_fd_sc_mcu7t5v0__buf_8 \u_regs/place3  (.I(\u_regs/rst_s ),
    .Z(\u_regs/net3 ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_row_dec/_23_  (.A1(row_sel[0]),
    .A2(row_sel[1]),
    .ZN(\u_row_dec/_00_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_row_dec/_24_  (.A1(row_sel[3]),
    .A2(row_sel[2]),
    .ZN(\u_row_dec/_01_ ));
 gf180mcu_fd_sc_mcu7t5v0__or2_2 \u_row_dec/_25_  (.A1(\u_row_dec/_00_ ),
    .A2(\u_row_dec/_01_ ),
    .Z(\u_row_dec/_02_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_row_dec/_26_  (.A1(row_sel[4]),
    .A2(dec_en),
    .ZN(\u_row_dec/_03_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_row_dec/_28_  (.A1(\u_row_dec/_02_ ),
    .A2(\u_row_dec/_03_ ),
    .ZN(row_onehot[31]));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_4 \u_row_dec/_29_  (.I(row_sel[0]),
    .ZN(\u_row_dec/_05_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_row_dec/_30_  (.A1(\u_row_dec/_05_ ),
    .A2(row_sel[1]),
    .ZN(\u_row_dec/_06_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_31_  (.A1(\u_row_dec/_01_ ),
    .A2(\u_row_dec/_03_ ),
    .A3(\u_row_dec/_06_ ),
    .ZN(row_onehot[30]));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 \u_row_dec/_32_  (.I(row_sel[1]),
    .ZN(\u_row_dec/_07_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_row_dec/_33_  (.A1(row_sel[0]),
    .A2(\u_row_dec/_07_ ),
    .ZN(\u_row_dec/_08_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_34_  (.A1(\u_row_dec/_01_ ),
    .A2(\u_row_dec/_03_ ),
    .A3(\u_row_dec/_08_ ),
    .ZN(row_onehot[29]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_row_dec/_35_  (.A1(row_sel[0]),
    .A2(row_sel[1]),
    .ZN(\u_row_dec/_09_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_row_dec/_36_  (.A1(row_sel[3]),
    .A2(row_sel[2]),
    .A3(\u_row_dec/_09_ ),
    .ZN(\u_row_dec/_10_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_row_dec/_37_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_10_ ),
    .ZN(row_onehot[28]));
 gf180mcu_fd_sc_mcu7t5v0__inv_4 \u_row_dec/_38_  (.I(row_sel[2]),
    .ZN(\u_row_dec/_11_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_row_dec/_39_  (.A1(row_sel[3]),
    .A2(\u_row_dec/_11_ ),
    .ZN(\u_row_dec/_12_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_40_  (.A1(\u_row_dec/_00_ ),
    .A2(\u_row_dec/_03_ ),
    .A3(\u_row_dec/_12_ ),
    .ZN(row_onehot[27]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_41_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_06_ ),
    .A3(\u_row_dec/_12_ ),
    .ZN(row_onehot[26]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_42_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_08_ ),
    .A3(\u_row_dec/_12_ ),
    .ZN(row_onehot[25]));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_row_dec/_43_  (.A1(\u_row_dec/_05_ ),
    .A2(\u_row_dec/_07_ ),
    .ZN(\u_row_dec/_13_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_44_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_13_ ),
    .A3(\u_row_dec/_12_ ),
    .ZN(row_onehot[24]));
 gf180mcu_fd_sc_mcu7t5v0__clkinv_3 \u_row_dec/_45_  (.I(row_sel[3]),
    .ZN(\u_row_dec/_14_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_2 \u_row_dec/_46_  (.A1(\u_row_dec/_14_ ),
    .A2(row_sel[2]),
    .ZN(\u_row_dec/_15_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_47_  (.A1(\u_row_dec/_00_ ),
    .A2(\u_row_dec/_03_ ),
    .A3(\u_row_dec/_15_ ),
    .ZN(row_onehot[23]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_48_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_06_ ),
    .A3(\u_row_dec/_15_ ),
    .ZN(row_onehot[22]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_49_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_08_ ),
    .A3(\u_row_dec/_15_ ),
    .ZN(row_onehot[21]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_50_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_13_ ),
    .A3(\u_row_dec/_15_ ),
    .ZN(row_onehot[20]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_row_dec/_51_  (.A1(row_sel[3]),
    .A2(row_sel[2]),
    .ZN(\u_row_dec/_16_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand3_1 \u_row_dec/_52_  (.A1(row_sel[0]),
    .A2(row_sel[1]),
    .A3(\u_row_dec/_16_ ),
    .ZN(\u_row_dec/_17_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_row_dec/_53_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_17_ ),
    .ZN(row_onehot[19]));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_row_dec/_54_  (.A1(\u_row_dec/_14_ ),
    .A2(\u_row_dec/_11_ ),
    .ZN(\u_row_dec/_18_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_55_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_06_ ),
    .A3(\u_row_dec/_18_ ),
    .ZN(row_onehot[18]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_56_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_08_ ),
    .A3(\u_row_dec/_18_ ),
    .ZN(row_onehot[17]));
 gf180mcu_fd_sc_mcu7t5v0__nand2_1 \u_row_dec/_57_  (.A1(\u_row_dec/_09_ ),
    .A2(\u_row_dec/_16_ ),
    .ZN(\u_row_dec/_19_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_row_dec/_58_  (.A1(\u_row_dec/_03_ ),
    .A2(\u_row_dec/_19_ ),
    .ZN(row_onehot[16]));
 gf180mcu_fd_sc_mcu7t5v0__inv_3 \u_row_dec/_59_  (.I(row_sel[4]),
    .ZN(\u_row_dec/_20_ ));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 \u_row_dec/_60_  (.A1(\u_row_dec/_20_ ),
    .A2(dec_en),
    .ZN(\u_row_dec/_21_ ));
 gf180mcu_fd_sc_mcu7t5v0__nor2_2 \u_row_dec/_62_  (.A1(\u_row_dec/_02_ ),
    .A2(\u_row_dec/_21_ ),
    .ZN(row_onehot[15]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_4 \u_row_dec/_63_  (.A1(\u_row_dec/_01_ ),
    .A2(\u_row_dec/_06_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[14]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_row_dec/_64_  (.A1(\u_row_dec/_01_ ),
    .A2(\u_row_dec/_08_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[13]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_row_dec/_65_  (.A1(\u_row_dec/_10_ ),
    .A2(\u_row_dec/_21_ ),
    .ZN(row_onehot[12]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_row_dec/_66_  (.A1(\u_row_dec/_00_ ),
    .A2(\u_row_dec/_12_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[11]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_row_dec/_67_  (.A1(\u_row_dec/_06_ ),
    .A2(\u_row_dec/_12_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[10]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_4 \u_row_dec/_68_  (.A1(\u_row_dec/_08_ ),
    .A2(\u_row_dec/_12_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[9]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_2 \u_row_dec/_69_  (.A1(\u_row_dec/_13_ ),
    .A2(\u_row_dec/_12_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[8]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_70_  (.A1(\u_row_dec/_00_ ),
    .A2(\u_row_dec/_15_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[7]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_71_  (.A1(\u_row_dec/_06_ ),
    .A2(\u_row_dec/_15_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[6]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_72_  (.A1(\u_row_dec/_08_ ),
    .A2(\u_row_dec/_15_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[5]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_73_  (.A1(\u_row_dec/_13_ ),
    .A2(\u_row_dec/_15_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[4]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_row_dec/_74_  (.A1(\u_row_dec/_17_ ),
    .A2(\u_row_dec/_21_ ),
    .ZN(row_onehot[3]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_75_  (.A1(\u_row_dec/_06_ ),
    .A2(\u_row_dec/_18_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[2]));
 gf180mcu_fd_sc_mcu7t5v0__nor3_1 \u_row_dec/_76_  (.A1(\u_row_dec/_08_ ),
    .A2(\u_row_dec/_18_ ),
    .A3(\u_row_dec/_21_ ),
    .ZN(row_onehot[1]));
 gf180mcu_fd_sc_mcu7t5v0__nor2_1 \u_row_dec/_77_  (.A1(\u_row_dec/_19_ ),
    .A2(\u_row_dec/_21_ ),
    .ZN(row_onehot[0]));
endmodule
