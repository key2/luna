`timescale 1ns/10ps

`include "static_macro_define.v"
`include "usb3_1_phy_name.v"
`include "usb3_1_phy_top_define.vh"

`ifdef MSIM
module usb3_1_phy
`else
module `getname(usb3_1_phy,`module_name) 
`endif
(
	input			    phy_resetn,
    `ifdef MSIM
    input               sys_clk_i,
    `endif
	input               ref_clk,
	//pipe interface
    output              pclk,
	input               PipeTxDataValid,
    input       [63:0]  PipeTxData,
    input       [3:0]   PipeTxSyncHead,
    input               PipeTxStartBlock,
    output      [63:0]  PipeRxData,
    output      [3:0]   PipeRxSyncHead,
    output              PipeRxStartBlock,
    output              PipeRxDataValid,

    input               TxDetectRx_loopback,
    input               TxElecIdle,
    input               RxPolarity,
    input               RxTermination,
    output              RxElecIdle,
    output  [2:0]       RxStatus,
    input   [1:0]       PowerDown,
    output              PhyStatus,
    output              PowerPresent,
    input               ElasticityBufferMode,

    //serdes interface
    input               serdes_upar_clk_i,
    output              serdes_upar_wren_o,
    output  [23:0]      serdes_upar_addr_o,
    output  [31:0]      serdes_upar_wrdata_o,
    output              serdes_upar_rden_o,
    input               serdes_upar_resp_i, 
    output  [7:0]       serdes_upar_strb_o,
    input   [31:0]      serdes_upar_rddata_i,
    input               serdes_upar_rdvld_i,
    input               serdes_upar_ready_i,
    input               serdes_q0_qpll0_ok_i,
    input               serdes_q0_qpll1_ok_i,
    input               serdes_q1_qpll0_ok_i,
    input               serdes_q1_qpll1_ok_i,
    input               serdes_cpll_ok_i,
    output              serdes_fabric_rstn_o,
    input               serdes_pcs_tx_clk_i,
    output              serdes_fabric_tx_clk_o,
    output              serdes_pcs_tx_rst_o,
    output  reg         serdes_fabric_tx_vld_o,
    input   [4:0]       serdes_tx_fifo_wrusewd_i,
    output  reg [79:0]  serdes_txdata_o,
    input               serdes_pcs_rx_clk_i,
    output              serdes_fabric_rx_clk_o,
    input               serdes_pma_rx_lock_i,
    output              serdes_pcs_rx_rst_o,
    output              serdes_rxfifo_rd_en_o,
    input               serdes_rxfifo_aempty_i,
    input   [4:0]       serdes_rx_fifo_rdusewd_i,
    input   [87:0]      serdes_rxdata_i,
    input               serdes_rx_vld_i,
    input               serdes_rxelecidle_i,
    input   [5:0]       serdes_astat_i
);

wire            sys_clk;
`ifdef MSIM
assign sys_clk = sys_clk_i;
`else
assign sys_clk = serdes_pcs_rx_clk_i;
`endif

reg             internel_resetn;
reg             phy_resetn_r0 = 1'b0;
reg             phy_resetn_r1 = 1'b0;
reg             tx_resetn = 1'b0;
reg             rx_resetn = 1'b0;
reg		[31:0]	tx_data_serdes;
reg		[3:0]	tx_data_serdes_k;
reg				tx_data_serdes_valid;
reg	    [63:0]	rx_data_serdes;
wire	[39:0]	rx_data_alignment;
wire    [39:0]  rx_data_buffer;
// wire	[3:0]	rx_data_serdes_k;
reg			    rx_data_serdes_valid;
wire			rx_data_alignment_valid;
wire            rx_data_buffer_valid;
wire            word_alignment_lock;
wire            serdes_pll_lock;
wire            serdes_rx_fifo_rd_en;

wire            add_skp;
wire            remove_skp;
wire            buffer_overflow;
wire            buffer_underflow;

wire	[63:0]	tx_data_encode_i;
wire	[3:0]	tx_data_sync_head_encode_i;
wire		    tx_data_start_block_encode_i;
wire		    tx_data_en_encode_i;

wire	[63:0]	tx_data_encode_o;
wire	[3:0]	tx_data_sync_head_encode_o;
wire		    tx_data_start_block_encode_o;
reg 		    tx_data_en_encode_o;
reg 	[63:0]	tx_data_encode_o_r;
reg 	[3:0]	tx_data_sync_head_encode_o_r;
reg 		    tx_data_start_block_encode_o_r;
reg 		    tx_data_en_encode_o_r;

wire	            rx_data_valid_8b10b_o;
wire	    [31:0]	rx_data_8b10b_o;
wire	    [3:0]	rx_data_k_8b10b_o;
wire	    [3:0]	rx_data_err_decode;

wire			poll_lfps;
wire			ping_lfps;
wire			reset_lfps;
wire			u1e_lfps;
wire			u2_loopback_lfps;
wire            lfps_detect;
wire            data_sel;
wire			tx_eidle;
wire			tx_eidle_ack;
reg			    tx_eidle_r0;
reg			    tx_eidle_r1;
wire			tx_detect_rx;
wire			tx_detect_rx_ack;
wire			tx_detect_rx_en;
reg			    tx_detect_rx_en_r0;
reg			    tx_detect_rx_en_r1;
wire			tx_ffe;
wire			tx_ffe_ack;
reg			    tx_ffe_r0;
reg			    tx_ffe_r1;

reg             c8b10b_en_r0;
reg             c8b10b_en_r1;

reg             RxPolarity_r0;
reg             RxPolarity_r1;
reg             upar_RxPolarity;

reg             upar_rstn_r0;
reg             upar_rstn_r1;
reg     [2:0]   upar_div_cnt = 0;
reg             upar_clk = 0;
wire            upar_wren; // input  None
wire    [23:0]  upar_addr; // input [23:0] None
wire    [31:0]  upar_wrdata; // input [31:0] None
wire            upar_rden; // input  None
wire    [31:0]  upar_rddata; // output [31:0] None
wire            upar_rdvld; // output  None
wire            upar_ready; // output  None

wire            pclk_o_en;

wire	[63:0]	rx_fifo_data;
wire	[4:0]	rx_fifo_rd_num;
wire	[4:0]	rx_fifo_wr_num;
wire			rx_fifo_empty;
wire	[39:0]	tx_fifo_data;
wire	[9:0]	tx_fifo_rd_num;
reg				tx_fifo_rd_en;
wire			tx_fifo_data_vld;

wire            rx_fifo_vld;
wire            tx_ready;
wire            tx_fifo_empty;

wire	    [63:0]	tx_elastic_data;
wire	    [3:0]	tx_elastic_data_k;
wire                tx_elastic_data_vld;
wire	    [63:0]	rx_elastic_data;
wire	    [3:0]	rx_elastic_sync_head;
wire	            rx_elastic_start_block;
wire                rx_elastic_data_vld;

wire [63:0] rx_fifo_dout;
wire [3:0] rx_fifo_sync_head;
wire rx_fifo_start_block;
wire rx_fifo_dout_vld;

assign serdes_upar_strb_o = 8'hff;
assign pclk_o_en = PowerDown == 2'b11 ? 1'b0 : 1'b1;

// DCE Inst_clk_out (
// .CLKIN(ref_clk), 
// .CE(pclk_o_en),
// .CLKOUT(pclk)
// );

assign pclk = serdes_pcs_tx_clk_i;

assign serdes_fabric_tx_clk_o = ref_clk;
assign serdes_fabric_rx_clk_o = pclk;
assign serdes_pcs_rx_rst_o = 1'b0;
assign serdes_pcs_tx_rst_o = 1'b0;
assign serdes_fabric_rstn_o = 1'b1;
assign serdes_rxfifo_rd_en_o = !serdes_rxfifo_aempty_i;
assign serdes_pll_lock = serdes_q0_qpll0_ok_i || serdes_q0_qpll1_ok_i || serdes_q1_qpll0_ok_i || serdes_q1_qpll1_ok_i || serdes_cpll_ok_i;

`ifdef MSIM
always@(posedge pclk)
`else
always@(posedge serdes_upar_clk_i)
`endif
begin
    upar_rstn_r0 <= internel_resetn;
    upar_rstn_r1 <= upar_rstn_r0;
    tx_detect_rx_en_r0 <= tx_detect_rx_en;
    tx_detect_rx_en_r1 <= tx_detect_rx_en_r0;
    tx_eidle_r0 <= tx_eidle;
    tx_eidle_r1 <= tx_eidle_r0;
    tx_ffe_r0 <= tx_ffe;
    tx_ffe_r1 <= tx_ffe_r0;
end

always@(posedge pclk)
begin
    `ifdef MSIM
    internel_resetn <= phy_resetn_r1;
    `else
    internel_resetn <= serdes_pll_lock && phy_resetn_r1;
    `endif
    phy_resetn_r0 <= phy_resetn;
    phy_resetn_r1 <= phy_resetn_r0;
end

always@(posedge pclk)
begin
    `ifdef MSIM
    tx_resetn <= phy_resetn_r1;
    `else
    tx_resetn <= serdes_pll_lock && phy_resetn_r1;
    `endif
end

always@(posedge pclk)
begin
    `ifdef MSIM
    rx_resetn <= phy_resetn_r1;
    `else
    rx_resetn <= serdes_pll_lock && phy_resetn_r1;
    `endif
end

always@(posedge ref_clk)
begin
    RxPolarity_r0 <= RxPolarity;
    RxPolarity_r1 <= RxPolarity_r0;
	
    rx_data_serdes_valid <= serdes_rx_vld_i;
    rx_data_serdes <= !RxPolarity_r1 ? serdes_rxdata_i[63:0] : ~serdes_rxdata_i[63:0];
end

// always@(posedge serdes_pcs_tx_clk_i)
always@(posedge pclk)
begin
	serdes_txdata_o <=  !data_sel ? {16'b0, tx_fifo_data} :  {16'b0, tx_data_encode_i};
    serdes_fabric_tx_vld_o <= !data_sel ? tx_fifo_data_vld : tx_data_en_encode_i;
	tx_fifo_rd_en <= serdes_tx_fifo_wrusewd_i < 10? 1'b1 : 1'b0;
    // rx_fifo_dout_vld <= ~rx_fifo_empty;
end

assign rx_fifo_data = rx_data_serdes;
assign rx_fifo_vld = rx_data_serdes_valid;

assign tx_fifo_data_vld = 1'b1;

`ifdef MSIM
usb_pipe_interface Inst_usb_pipe_interface
`else
`getname(usb_pipe_interface,`module_name) Inst_usb_pipe_interface
`endif
(
    .pclk                   (pclk),//input               
    .pcs_clk                (pclk),//input        
    .reset                  (~internel_resetn),//input                
    .TxValid                (rx_fifo_dout_vld),//input               
    .TxData                 (rx_fifo_dout),//input       [63:0]  
    .TxSyncHead             (rx_fifo_sync_head),//input       [3:0]   
    .TxStartBlock           (rx_fifo_start_block),//input      
    .RxValid                (tx_data_en_encode_i),//output  reg         
    .RxData                 (tx_data_encode_i),//output  reg [63:0]  
    .RxSyncHead             (tx_data_sync_head_encode_i),//output  reg [3:0]   
    .RxStartBlock           (tx_data_start_block_encode_i),//output  reg
    .data_sel               (data_sel),//output  reg         
    .pll_lock               (serdes_pll_lock),//input               
    .lfps_detect            (lfps_detect),//input               
    .serdes_astat           (serdes_astat_i),
    .rx_data_err            (rx_data_err_decode),
	.tx_detect_rx_en		(tx_detect_rx_en),
	.tx_detect_rx_ack		(tx_detect_rx_ack),
	.tx_detect_rx			(tx_detect_rx),
	.tx_eidle				(tx_eidle),
	.tx_eidle_ack			(tx_eidle_ack),
	.tx_ffe                 (tx_ffe),
	.tx_ffe_ack             (tx_ffe_ack),
    .PipeTxDataValid        (PipeTxDataValid    ),//input  
    .PipeTxData             (PipeTxData     ),//input       [63:0]  
    .PipeTxSyncHead         (PipeTxSyncHead    ),//input       [3:0]   
    .PipeTxStartBlock       (PipeTxStartBlock    ),//input  
    .PipeRxData             (PipeRxData     ),//output  reg [63:0]  
    .PipeRxSyncHead         (PipeRxSyncHead    ),//output  reg [3:0]   
    .PipeRxStartBlock       (PipeRxStartBlock),//output  reg         
    .PipeRxDataValid        (PipeRxDataValid),//output  reg         
    .TxDetectRx_loopback    (TxDetectRx_loopback ),//input               
    .TxElecIdle             (TxElecIdle          ),//input               
    // .TxOnesZeros            (TxOnesZeros         ),//input               //
    // .TxDeemph               (TxDeemph            ),//input   [1:0]       //
    // .TxMargin               (TxMargin            ),//input   [2:0]       //
    // .TxSwing                (TxSwing             ),//input               //
    .RxPolarity             (RxPolarity          ),//input               
    // .RxEqTraining           (RxEqTraining        ),//input               //
    .RxTermination          (RxTermination       ),//input               
    .RxElecIdle             (RxElecIdle          ),//output              
    .RxStatus               (RxStatus            ),//output  reg [2:0]   
    .ElasticityBufferMode   (ElasticityBufferMode),//input               
    .PowerDown              (PowerDown           ),//input   [1:0]       
    .Rate                   (Rate                ),//input               //
    .PhyStatus              (PhyStatus           ),//output              
    .PowerPresent           (PowerPresent        )//output              
);

`ifdef MSIM
datapath Inst_datapath
`else
`getname(datapath,`module_name) Inst_datapath
`endif
(
    .i_rx_clk           (pclk), //input	wire		            
    .i_tx_clk           (pclk), //input	wire		            
    .i_reset_n          (internel_resetn), //input	wire		            
    .i_sys_clk          (pclk), //input	wire		            
    .i_fast_clk         (pclk), //input	wire		            
    .i_raw_data_valid   (rx_fifo_vld), //input	wire	        
    .i_raw_data         (rx_fifo_data), //input	wire	[63:0]	    
    .o_raw_data         (tx_fifo_data), //output	reg	[63:0]	        
    .S_VALID            (tx_data_en_encode_o_r), //input	wire				    
    .S_READY            (tx_ready), //output	wire				    
    .S_DATA             (tx_data_encode_o_r), //input	wire	[63:0]		
    .S_SYNCHEAD         (tx_data_sync_head_encode_o_r), //input	wire	[3:0]		    
    .S_STARTBLOCK       (tx_data_start_block_encode_o_r), //input	wire				    
    .M_VALID            (rx_fifo_dout_vld), //output	wire				    
    .M_READY            (1'b1), //input	wire				    
    .M_DATA             (rx_fifo_dout), //output	wire	[63:0]		
    .M_SYNCHEAD         (rx_fifo_sync_head), //output	wire	[3:0]		    
    .M_STARTBLOCK       (rx_fifo_start_block)  //output	wire				     
);

`ifdef MSIM
async_fifo
`else
`getname(async_fifo,`module_name)
`endif
#(
    .DSIZE 			(69), //parameter             = 40,
    .ASIZE 			(5), //parameter             = 10,
    .AEMPT 			(1), //parameter             = 1,
    .AFULL 			(31)  //parameter             = 32
)
Inst_tx_async_fifo
(
    .Q				({tx_data_encode_o, tx_data_sync_head_encode_o, tx_data_start_block_encode_o}), //output reg [DSIZE-1:0]   	
    .Full			(), //output reg               	
    .Empty			(tx_fifo_empty), //output reg               	
    .AlmostEmpty	(), //output reg               	
    .AlmostFull		(), //output reg               	
    .RdDataNum		(), //output reg [ASIZE:0]   	
    .WrDataNum		(), //output reg [ASIZE:0]   	
    .Data			({tx_data_encode_i, tx_data_sync_head_encode_i, tx_data_start_block_encode_i}), //input   [DSIZE-1:0]   	
    .WrEn			(tx_data_en_encode_i && ~data_sel), //input                 	
    .WrClock		(pclk), //input                 	            	
    .WPReset		(~internel_resetn), //input                 	
    .RdEn			(tx_ready && tx_fifo_empty), //input                 	
    .RdClock		(pclk), //input                 	
    .RPReset		(~internel_resetn)  //input                 	
);

always@(posedge pclk or negedge internel_resetn) begin
    if(!internel_resetn) begin
        tx_data_encode_o_r <= 0;
        tx_data_sync_head_encode_o_r <= 0;
        tx_data_start_block_encode_o_r <= 0;
        tx_data_en_encode_o_r <= 0;
        tx_data_en_encode_o <= 0;
    end
    else begin
        tx_data_en_encode_o <= 1;
        tx_data_en_encode_o_r <= tx_data_en_encode_o;
        if(tx_ready && tx_fifo_empty) begin
            tx_data_encode_o_r <= tx_data_encode_o;
            tx_data_sync_head_encode_o_r <= tx_data_sync_head_encode_o;
            tx_data_start_block_encode_o_r <= tx_data_start_block_encode_o;
        end
    end
end

`ifndef MSIM
`getname(upar_csr,`module_name) Inst_upar_csr
(
    .clk_in(serdes_upar_clk_i),
    .rst_n(upar_rstn_r1),
    .c8b10b_en(1'b1),
    .rx_polarity(1'b0),
    .eidle_en(tx_eidle_r1),
	.eidle_en_ack(tx_eidle_ack),
	.tx_detect_rx_en(tx_detect_rx_en_r1),
	.tx_detect_rx_ack(tx_detect_rx_ack),
	.tx_detect_rx(tx_detect_rx),
    .ffe_en(tx_ffe_r1),
    .ffe_en_ack(tx_ffe_ack),
    .upar_wren( serdes_upar_wren_o            ) , // input  None
    .upar_addr( serdes_upar_addr_o            ) , // input [23:0] None
    .upar_wrdata( serdes_upar_wrdata_o          ) , // input [31:0] None
    .upar_rden( serdes_upar_rden_o            ) , // input  None
    .upar_rddata( serdes_upar_rddata_i          ) , // output [31:0] None
    .upar_rdvld( serdes_upar_rdvld_i           ) , // output  None
    .upar_ready_i( serdes_upar_ready_i           ) // output  None
);
`else
always@(posedge pclk)
begin
	tx_detect_rx <= tx_detect_rx_en_r1;
end
`endif

// `ifdef MSIM
// elastic_buffer Inst_rx_elastic_buffer
// `else
// `getname(elastic_buffer,`module_name) Inst_rx_elastic_buffer
// `endif
// (
//     .clkin          (ref_clk),//input	wire			
//     .resetn         (internel_resetn),//input	wire			
//     .tx_fifo_used   (rx_fifo_wr_num),
//     .raw_valid      (rx_data_valid_8b10b_o),//input	wire		    
//     .raw_datak      ({rx_data_k_8b10b_o[0], rx_data_k_8b10b_o[1], rx_data_k_8b10b_o[2], rx_data_k_8b10b_o[3]}),//input	wire	[3:0]	
//     .raw_data       ({rx_data_8b10b_o[7:0], rx_data_8b10b_o[15:8], rx_data_8b10b_o[23:16], rx_data_8b10b_o[31:24]}),//input	wire	[31:0]	
//     .proc_datak     ({rx_elastic_sync_head[0], rx_elastic_sync_head[1], rx_elastic_sync_head[2], rx_elastic_sync_head[3]}),//output	wire	[3:0]	
//     .proc_data      ({rx_elastic_data[7:0], rx_elastic_data[15:8], rx_elastic_data[23:16], rx_elastic_data[31:24]}),//output	wire	[31:0]	
//     .proc_active    (rx_elastic_data_vld) //output	wire			
// );

// `ifdef MSIM
// async_fifo
// `else
// `getname(async_fifo,`module_name)
// `endif
// #(
//     .DSIZE 			(69), //parameter             = 40,
//     .ASIZE 			(5), //parameter             = 10,
//     .AEMPT 			(1), //parameter             = 1,
//     .AFULL 			(31)  //parameter             = 32
// )
// Inst_rx_async_fifo
// (
//     .Q				({rx_fifo_dout, rx_fifo_sync_head, rx_fifo_start_block}), //output reg [DSIZE-1:0]   	
//     .Full			(), //output reg               	
//     .Empty			(rx_fifo_empty), //output reg               	
//     .AlmostEmpty	(), //output reg               	
//     .AlmostFull		(), //output reg               	
//     .RdDataNum		(), //output reg [ASIZE:0]   	
//     .WrDataNum		(rx_fifo_wr_num), //output reg [ASIZE:0]   	
//     .Data			({rx_elastic_data, rx_elastic_sync_head, rx_elastic_start_block}), //input   [DSIZE-1:0]   	
//     .WrEn			(rx_elastic_data_vld), //input                 	
//     .WrClock		(ref_clk), //input                 	            	
//     .WPReset		(~internel_resetn), //input                 	
//     .RdEn			(1'b1), //input                 	
//     .RdClock		(pclk), //input                 	
//     .RPReset		(~internel_resetn)  //input                 	
// );

// `ifdef MSIM
// elastic_buffer Inst_tx_elastic_buffer
// `else
// `getname(elastic_buffer,`module_name) Inst_tx_elastic_buffer
// `endif
// (
    // .clkin          (pclk),//input	wire			
    // .resetn         (internel_resetn),//input	wire			
    // .tx_fifo_used   (serdes_tx_fifo_wrusewd_i),
    // .raw_valid      (tx_data_en_encode_i),//input	wire		    
    // .raw_datak      ({tx_data_k_8b10b_i[0], tx_data_k_8b10b_i[1], tx_data_k_8b10b_i[2], tx_data_k_8b10b_i[3]}),//input	wire	[3:0]	
    // .raw_data       ({tx_data_8b10b_i[7:0], tx_data_8b10b_i[15:8], tx_data_8b10b_i[23:16], tx_data_8b10b_i[31:24]}),//input	wire	[31:0]	
    // .proc_datak     ({tx_elastic_data_k[0], tx_elastic_data_k[1], tx_elastic_data_k[2], tx_elastic_data_k[3]}),//output	wire	[3:0]	
    // .proc_data      ({tx_elastic_data[7:0], tx_elastic_data[15:8], tx_elastic_data[23:16], tx_elastic_data[31:24]}),//output	wire	[31:0]	
    // .proc_active    (tx_elastic_data_vld) //output	wire			
// );

`ifdef MSIM
usb3_lfps_detector Inst_usb3_lfps_detector
`else
`getname(usb3_lfps_detector,`module_name) Inst_usb3_lfps_detector
`endif
(
    .clk				(pclk), //input           //125MHz
    .rstn				(internel_resetn), //input           
    .rx_data			(rx_fifo_dout), //input   [39:0]  
    .lfps_detect        (lfps_detect)
);



endmodule

`ifdef MSIM
module usb_pipe_interface
`else
module `getname( usb_pipe_interface,`module_name)
`endif
(
    input               pclk,
    input               pcs_clk,
    output              pclk_o,
    input               reset,

    //to next module
    input               TxValid,
    input       [63:0]  TxData,
    input       [3:0]   TxSyncHead,
    input               TxStartBlock,
    output  reg         RxValid,
    output  reg [63:0]  RxData,
    output  reg [3:0]   RxSyncHead,
    output  reg         RxStartBlock,
    output  reg         data_sel,
    input               pll_lock,
    input               lfps_detect,
    input       [5:0]   serdes_astat,
    input               rx_data_err,
	output	reg			tx_eidle,
	input				tx_eidle_ack,
	output	reg			tx_detect_rx_en,
	input				tx_detect_rx_ack,
	input				tx_detect_rx,
	output	reg			tx_ffe,
	input				tx_ffe_ack,

    //to interface
    input               PipeTxDataValid,
    input       [63:0]  PipeTxData,
    input       [3:0]   PipeTxSyncHead,
    input               PipeTxStartBlock,
    output  reg [63:0]  PipeRxData,
    output  reg [3:0]   PipeRxSyncHead,
    output  reg         PipeRxStartBlock,
    output  reg         PipeRxDataValid,

    input               TxDetectRx_loopback,
    input               TxElecIdle,
    input               TxOnesZeros,//
    input   [1:0]       TxDeemph,//
    input   [2:0]       TxMargin,//
    input               TxSwing,//

    input               RxPolarity,
    input               RxEqTraining,//
    input               RxTermination,
    output              RxElecIdle,
    output  reg [2:0]   RxStatus,

    input               ElasticityBufferMode,
    input   [1:0]       PowerDown,
    input               Rate,//
    output  reg         PhyStatus,
    output              PowerPresent
);

//parameter 
//    P0      = 4'd0,
//    P1      = 4'd1,
//    P2      = 4'd2,
//    P3      = 4'd3,
//	LFPS_0	= 4'd4,
//	LFPS_1	= 4'd5,
//	LFPS_2	= 4'd6,
//	LFPS_3	= 4'd7,
//    ONEZERO = 4'd8,
//    RXTERM  = 4'd9,
//    RX_EQ   = 4'd10,
//    IDLE    = 4'd11;
parameter 
    P0      = 4'b0000,
    P1      = 4'b0001,
    P2      = 4'b0011,
    P3      = 4'b0010,
	LFPS_0	= 4'b0110,
	LFPS_1	= 4'b0111,
	LFPS_2	= 4'b0101,
	LFPS_3	= 4'b0100,
    ONEZERO = 4'b1100,
    RXTERM  = 4'b1101,
    RX_EQ   = 4'b1111,
    IDLE    = 4'b1110;

reg     [3:0]   c_state;
reg     [1:0]   n_state;
reg             onezero_done;
reg     [15:0]  cnt0;
reg     [3:0]   cnt1;
reg     [7:0]   cnt2;
reg		[7:0]	lfps_cnt;
reg		[7:0]	lfps_time_out_cnt;
reg		[7:0]	lfps_wait_cnt;
reg				lfps_en;
reg     [1:0]   PowerDown_r = 2'b10;
reg     [5:0]   serdes_astat_r0;
reg     [5:0]   serdes_astat_r1;
reg     [5:0]   serdes_astat_r2;
reg             serdes_astat_filter;
reg             TxDetectRx_loopback_r0;
reg             TxDetectRx_loopback_r1;
reg             TxElecIdle_r0;
reg             TxElecIdle_r1;
reg             signal_detected;
reg     [7:0]  reset_r = 8'b0;

reg             tx_detect_rx_ack_r0;
reg             tx_detect_rx_ack_r1;
reg             tx_detect_rx_r0;
reg             tx_detect_rx_r1;

reg             first_lfps = 1'b0;
reg             cdr_timeout = 1'b0;
reg     [31:0]  cnt_timeout = 0;

always@(posedge pclk)
begin
    tx_detect_rx_ack_r0 <= tx_detect_rx_ack;
    tx_detect_rx_ack_r1 <= tx_detect_rx_ack_r0;
    tx_detect_rx_r0 <= tx_detect_rx;
    tx_detect_rx_r1 <= tx_detect_rx_r0;
end

`ifdef MSIM
assign RxElecIdle = !lfps_detect;
`else
assign RxElecIdle = !first_lfps || cdr_timeout ? !serdes_astat_filter : !lfps_detect;
`endif
assign PowerPresent = 1'b1;

always@(posedge pclk or posedge reset)
begin
    if(reset)
    begin
        lfps_cnt <= 0;
		lfps_time_out_cnt <= 0;
    end
    else
    begin
		lfps_time_out_cnt <= 0;
        if(PowerDown == P0 && TxElecIdle && TxDetectRx_loopback)
		begin
			if(lfps_en)
			begin
				lfps_cnt <= lfps_cnt;
			end
			else
			begin
				lfps_cnt <= lfps_cnt + 1;
			end
		end
		if((PowerDown == P1 || PowerDown == P2 || PowerDown == P3) && !TxElecIdle)
		begin
			if(lfps_en)
			begin
				lfps_cnt <= lfps_cnt;
			end
			else
			begin
				lfps_cnt <= lfps_cnt + 1;
			end
		end
		else if(lfps_en)
		begin
			lfps_cnt <= lfps_cnt - 1;
		end
		else
		begin
			if(lfps_time_out_cnt == 255)
			begin
				lfps_cnt <= 0;
			end
			else
			begin
				lfps_cnt <= lfps_cnt;
				lfps_time_out_cnt <= lfps_time_out_cnt + 1'b1;
			end
		end
    end
end

always@(posedge pclk or posedge reset)
begin
	if(reset)
	begin
		first_lfps <= 1'b0;
        cdr_timeout <= 1'b0;
        cnt_timeout <= 0;
        serdes_astat_r2 <= 0;
        serdes_astat_filter <= 1'b0;
	end
	else
	begin
        serdes_astat_r2 <= {serdes_astat_r2[4:0], serdes_astat_r0[5]};
        if(serdes_astat_r2 == 6'b000000)
        begin
            serdes_astat_filter <= 1'b0;
        end
        else if(serdes_astat_r2 == 6'b111111)
        begin
            serdes_astat_filter <= 1'b1;
        end

		if((PowerDown_r == P0) || (PowerDown_r == P1))
		begin
			first_lfps <= 1'b1;
		end
		else 
		begin
			first_lfps <= 1'b0;
		end

        if(cnt_timeout > 1250000)
        begin
            cdr_timeout <= 1'b1;
        end
        else
        begin
            cdr_timeout <= 1'b0;
        end

        if(!TxValid)
        begin
            if(cnt_timeout <= 1250000)
                cnt_timeout <= cnt_timeout + 1'b1;
            else
                cnt_timeout <= cnt_timeout;
        end
        else
        begin
            cnt_timeout <= 0;
        end
	end
end

always@(posedge pclk)
begin
    if(cnt2 == 254)
    begin
        PhyStatus           <= 1'b1;
    end
	else if(tx_detect_rx_ack_r0 && ~tx_detect_rx_ack_r1)
	begin
		PhyStatus           <= 1'b1;
	end
    else if(PowerDown_r != 2'b00 && PowerDown == 2'b00)
    begin
        PhyStatus           <= 1'b1;
    end
    else if(PowerDown_r != 2'b01 && PowerDown == 2'b01)
    begin
        PhyStatus           <= 1'b1;
    end
    else if(PowerDown_r != 2'b10 && PowerDown == 2'b10)
    begin
        PhyStatus           <= 1'b1;
    end
    else
    begin
        PhyStatus           <= 1'b0;
    end
end

always@(posedge pclk or posedge reset)
begin
	if(reset)
	begin
		cnt2 <= 0;
	end
	else
	begin
		if(cnt2 < 255)
		begin
			cnt2 <= cnt2 + 1'b1;
		end
	end
end

always@(posedge pclk)
begin
    RxStatus <= 3'b000;
    PowerDown_r <= PowerDown;
	if(PowerDown_r == 2'b10)
	begin
		if(TxDetectRx_loopback_r1 && TxElecIdle_r1)
		begin
			tx_detect_rx_en <= 1'b1;
		end
		else if(tx_detect_rx_ack_r0 && ~tx_detect_rx_ack_r1)
		begin
			tx_detect_rx_en <= 1'b0;
		end
        else
        begin
            tx_detect_rx_en <= 1'b0;
        end
	end
	else if(PowerDown_r == 2'b11)
	begin
		if(TxElecIdle)
		begin
			tx_detect_rx_en <= 1'b1;
		end
		else if(tx_detect_rx_ack_r0 && ~tx_detect_rx_ack_r1)
		begin
			tx_detect_rx_en <= 1'b0;
		end
        else
        begin
            tx_detect_rx_en <= 1'b0;
        end
	end
	else 
	begin
		tx_detect_rx_en <= 1'b0;
	end
    
	if(tx_detect_rx_r0 && ~tx_detect_rx_r1)
	begin
		RxStatus            <= 3'b011;
	end
    else if(rx_data_err && PowerDown_r == 2'b00 && !lfps_detect)
    begin
        RxStatus            <= 3'b100;
    end
    else
    begin
        RxStatus            <= 3'b000;
    end
end

always@(posedge pclk or posedge reset)
begin
    if(reset)
    begin
        serdes_astat_r0 <= 6'b0;
        serdes_astat_r1 <= 6'b0;
        TxDetectRx_loopback_r0 <= 1'b0;
        TxDetectRx_loopback_r1 <= 1'b0;
        TxElecIdle_r0 <= 1'b1;
        TxElecIdle_r1 <= 1'b1;
        signal_detected <= 1'b0;
    end
    else
    begin
        serdes_astat_r0 <= serdes_astat;
        serdes_astat_r1 <= serdes_astat_r0;
        TxDetectRx_loopback_r0 <= TxDetectRx_loopback;
        TxDetectRx_loopback_r1 <= TxDetectRx_loopback_r0;
        TxElecIdle_r0 <= TxElecIdle;
        TxElecIdle_r1 <= TxElecIdle_r0;
        if(serdes_astat_r0[5] & !serdes_astat_r1[5])
        begin
            signal_detected <= 1'b1;
        end
    end
end

always@(posedge pclk or posedge reset)
begin
    if(reset)
    begin
        PipeRxDataValid     <= 1'b0;
        PipeRxData          <= 64'h0;
        PipeRxSyncHead      <= 4'b1100;
        PipeRxStartBlock    <= 1'b0;
        RxValid             <= 1'b0;
        RxData              <= 64'h0;
        RxSyncHead          <= 4'b1100;
        RxStartBlock        <= 1'b0;
        cnt0                <= 16'd0;
        cnt1                <= 4'd0;
		lfps_wait_cnt		<= 0;
        onezero_done        <= 1'b0;
        data_sel            <= 1'b1;
		tx_eidle			<= 1'b1;
		lfps_en				<= 1'b0;
        tx_ffe              <= 1'b1;
    end
    else
    begin
        onezero_done        <= 1'b0;
        data_sel            <= 1'b0;
        case(c_state)
            P0 : 
            begin
                tx_ffe              <= 1'b0;
                if(!TxElecIdle_r1)
                begin
                    data_sel            <= 1'b0;
				    tx_eidle			<= 1'b0;
                    if(!TxDetectRx_loopback_r1)
                    begin
                        PipeRxDataValid     <= !lfps_detect? TxValid : 1'b0;
                        PipeRxData          <= TxData;
                        PipeRxSyncHead      <= TxSyncHead;
                        PipeRxStartBlock    <= TxStartBlock;
                        RxValid             <= PipeTxDataValid;
                        RxData              <= PipeTxData;
                        RxSyncHead          <= PipeTxSyncHead;
                        RxStartBlock        <= PipeTxStartBlock;
                    end
                    else
                    begin
                        PipeRxDataValid     <= TxValid;
                        PipeRxData          <= TxData;
                        PipeRxSyncHead      <= TxSyncHead;
                        PipeRxStartBlock    <= TxStartBlock;
                        RxValid             <= TxValid;
                        RxData              <= TxData;
                        RxSyncHead          <= TxSyncHead;
                        RxStartBlock        <= TxStartBlock;
                    end
                end
                else
                begin
                    data_sel            <= 1'b1;
                    if(!TxDetectRx_loopback_r1)
                    begin
                        PipeRxDataValid     <= 1'b0;
                        PipeRxData          <= 64'h0;
                        PipeRxSyncHead      <= 4'b1100;
                        PipeRxStartBlock    <= 1'b0;
                        RxValid             <= 1'b1;
						RxData              <= 64'hAAAAAAAAAAAAAAAA;
						RxSyncHead          <= 4'b1100;
						RxStartBlock        <= 1'b0;
						tx_eidle			<= 1'b1;
                    end
                end
            end

            P1 :
            begin
                data_sel            <= 1'b1;
				tx_eidle			<= 1'b1;
				PipeRxDataValid     <= 1'b0;
				PipeRxData          <= 64'h0;
				PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
				RxValid             <= 1'b1;
				RxData              <= 64'hAAAAAAAAAAAAAAAA;
				RxSyncHead          <= 4'b1100;
                RxStartBlock        <= 1'b0;
            end

            P2 : 
            begin
                data_sel            <= 1'b1;
				cnt0				<= 16'd0;
				tx_eidle			<= 1'b1;
				PipeRxDataValid     <= 1'b0;
				PipeRxData          <= 64'h0;
				PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
				RxValid             <= 1'b1;
				RxData              <= 64'hAAAAAAAAAAAAAAAA;
				RxSyncHead          <= 4'b1100;
                RxStartBlock        <= 1'b0;
            end

            P3 : 
            begin
                data_sel            <= 1'b1;
				cnt0				<= 16'd0;
				tx_eidle			<= 1'b1;
				PipeRxDataValid     <= 1'b0;
				PipeRxData          <= 64'h0;
				PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
				RxValid             <= 1'b1;
				RxData              <= 64'hAAAAAAAAAAAAAAAA;
				RxSyncHead          <= 4'b1100;
                RxStartBlock        <= 1'b0;
            end
			
			LFPS_0 : 
			begin
                data_sel            <= 1'b1;
				PipeRxDataValid     <= 1'b0;
				PipeRxData          <= 64'h0;
				PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
				tx_ffe			    <= 1'b1;
				lfps_en				<= 1'b0;
				cnt1				<= 0;
				RxValid             <= 1'b1;
				RxData              <= 64'hAAAAAAAAAAAAAAAA;
				RxSyncHead          <= 4'b1100;
                RxStartBlock        <= 1'b0;
				
			end
			
			LFPS_1 : 
			begin
				lfps_wait_cnt		<= lfps_wait_cnt + 1'b1;
                data_sel            <= 1'b1;
				PipeRxDataValid     <= 1'b0;
				PipeRxData          <= 64'h0;
				PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
//				tx_eidle			<= 1'b0;
				lfps_en				<= 1'b0;
				cnt1				<= 0;
				RxValid             <= 1'b0;
				RxData              <= 64'hAAAAAAAAAAAAAAAA;
				RxSyncHead          <= 4'b0000;
                RxStartBlock        <= 1'b0;
				if(lfps_wait_cnt <= 15) begin
                    tx_eidle			<= 1'b1;
                end
                else begin
                    tx_eidle			<= 1'b0;
                end
			end
			
			LFPS_2 : 
			begin
				lfps_wait_cnt		<= 0;
                data_sel            <= 1'b1;
				lfps_en				<= 1'b1;
				cnt1                <= cnt1 + 1'b1;
				RxValid             <= 1'b1;
                RxStartBlock        <= 1'b0;
                RxSyncHead          <= 4'b1100;
                if(lfps_cnt <= 18)
                    tx_eidle			<= 1'b1;
                else
                    tx_eidle			<= 1'b0;
				if(cnt1[2])
				begin
					RxData              <= 64'h0000000000000000;
				end
				else
				begin
					RxData              <= 64'hFFFFFFFFFFFFFFFF;
				end
			end
			
			LFPS_3 : 
			begin
                data_sel            <= 1'b1;
				lfps_en				<= 1'b0;
				cnt1				<= 0;
				// tx_eidle			<= 1'b1;
				PipeRxDataValid     <= 1'b0;
				PipeRxData          <= 64'h0;
				PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
				RxValid             <= 1'b1;
				RxData              <= 64'hAAAAAAAAAAAAAAAA;
				RxSyncHead          <= 4'b1100;
                RxStartBlock        <= 1'b0;
			end

            //ONEZERO : 
            //begin
            //    data_sel            <= 1'b1;
            //    if(cnt0 < 400)
            //    begin
            //        cnt0                <= cnt0 + 1'b1;
            //        PipeRxDataValid     <= TxValid;
            //        PipeRxData          <= TxData;
            //        PipeRxSyncHead      <= TxSyncHead;
            //        PipeRxStartBlock    <= TxStartBlock;
            //        RxValid             <= 1'b1;
            //        RxData              <= 64'hAAAAAAAAAAAAAAAA;
            //        RxSyncHead          <= 4'b1100;
            //        RxStartBlock        <= 1'b0;
            //    end
            //    else
            //    begin
            //        cnt0                <= 16'd0;
            //        onezero_done        <= 1'b1;
            //        PipeRxDataValid     <= TxValid;
            //        PipeRxData          <= TxData;
            //        PipeRxSyncHead      <= TxSyncHead;
            //        RxValid             <= 1'b1;
            //        RxData              <= 64'hAAAAAAAAAAAAAAAA;
            //        RxSyncHead          <= 4'b0000;
            //        RxStartBlock        <= 1'b0;
            //    end
            //end

            RXTERM : 
            begin
                PipeRxDataValid     <= TxValid;
                PipeRxData          <= TxData;
                PipeRxSyncHead         <= TxSyncHead;
                PipeRxStartBlock    <= 1'b0;
                RxValid             <= 1'b1;
                RxData              <= 32'h00000000;
                RxSyncHead             <= 4'b0;
                RxStartBlock        <= 1'b0;
            end

            //RX_EQ : 
            //begin
            //    PipeRxDataValid     <= 1'b0;
            //    PipeRxData          <= 64'b0;
            //    PipeRxSyncHead      <= 4'b1100;
            //    PipeRxStartBlock    <= 1'b0;
            //    RxValid             <= 1'b1;
            //    RxData              <= 64'h00000000;
            //    RxSyncHead          <= 4'b1100;
            //    RxStartBlock        <= 1'b0;
            //end

            IDLE : 
            begin
                PipeRxDataValid     <= 1'b0;
                PipeRxData          <= 64'b0;
                PipeRxSyncHead      <= 4'b1100;
                PipeRxStartBlock    <= 1'b0;
                RxValid             <= 1'b1;
                RxData              <= 64'h00000000;
                RxSyncHead          <= 4'b1100;
                RxStartBlock        <= 1'b0;
            end
        endcase
    end
end

always@(posedge pclk or posedge reset)
begin: NEXT_STATE_ASSIGNMENT
    if (reset)
        c_state    <=  IDLE;	
    else 
	begin
        case(c_state)
            P0 : 
            begin
				if(TxElecIdle && TxDetectRx_loopback)
				begin
                    if(tx_ffe) begin
					    c_state     <= LFPS_1;
                    end
                    else begin
                        c_state     <= LFPS_0;
                    end
				end
                else if(TxOnesZeros)
                begin
                    c_state     <= ONEZERO;
                end
                else if(!RxTermination)
                begin
                    c_state     <= RXTERM;
                end
                else if(PowerDown != PowerDown_r)
                begin
					if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else if(RxEqTraining)
                begin
                    c_state     <= RX_EQ;
                end
                else 
                begin
                    c_state    <=  c_state;	
                end
            end

            P1 : 
            begin
				if(!TxElecIdle)
				begin
					if(tx_ffe) begin
					    c_state     <= LFPS_1;
                    end
                    else begin
                        c_state     <= LFPS_0;
                    end
				end
                else if(TxOnesZeros)
                begin
                    c_state     <= ONEZERO;
                end
                else if(PowerDown != PowerDown_r)
                begin
                    if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else if(RxEqTraining)
                begin
                    c_state     <= RX_EQ;
                end
                else 
                begin
                    c_state    <=  c_state;	
                end
            end

            P2 : 
            begin
				if(!TxElecIdle)
				begin
					if(tx_ffe) begin
					    c_state     <= LFPS_1;
                    end
                    else begin
                        c_state     <= LFPS_0;
                    end
				end
                else if(TxOnesZeros)
                begin
                    c_state     <= ONEZERO;
                end
                else if(PowerDown != PowerDown_r)
                begin
                    if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else if(RxEqTraining)
                begin
                    c_state     <= RX_EQ;
                end
                else 
                begin
                    c_state    <=  c_state;	
                end
            end

            P3 : 
            begin
				if(!TxElecIdle)
				begin
					if(tx_ffe) begin
					    c_state     <= LFPS_1;
                    end
                    else begin
                        c_state     <= LFPS_0;
                    end
				end
                else if(TxOnesZeros)
                begin
                    c_state     <= ONEZERO;
                end
                else if(PowerDown != PowerDown_r)
                begin
                    if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else if(RxEqTraining)
                begin
                    c_state     <= RX_EQ;
                end
                else 
                begin
                    c_state    <=  c_state;	
                end
            end
            
            LFPS_0 : 
			begin
				if(tx_ffe_ack)
				begin
					c_state     <= LFPS_1;
				end
                else 
                begin
                    c_state    <=  LFPS_0;	
                end
			end
			
			LFPS_1 : 
			begin
//				if(tx_eidle_ack)
//				begin
//					c_state     <= LFPS_2;
//				end
                if(lfps_wait_cnt == 33) begin
                    c_state     <= LFPS_2;
                end
				else if(lfps_cnt == 0)
				begin
					if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
				end
                else 
                begin
                    c_state    <=  LFPS_1;	
                end
			end
			
			LFPS_2 : 
			begin
				if(lfps_cnt <= 2)
				begin
					c_state     <= LFPS_3;
				end
                else 
                begin
                    c_state    <=  LFPS_2;	
                end
			end
			
			LFPS_3 : 
			begin
				if(PowerDown == 2'b00)
				begin
					c_state		<= P0;
				end
				else if(PowerDown == 2'b01)
				begin
					c_state		<= P1;
				end
				else if(PowerDown == 2'b10)
				begin
					c_state		<= P2;
				end
				else if(PowerDown == 2'b11)
				begin
					c_state		<= P3;
				end
			end

            ONEZERO : 
            begin
                if(onezero_done)
                begin
                    if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else 
                begin
                    c_state    <=  ONEZERO;	
                end
            end

            RXTERM : 
            begin
                if(RxTermination)
                begin
                    if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else 
                begin
                    c_state    <=  RXTERM;	
                end
            end

            RX_EQ : 
            begin
                if(!RxEqTraining)
                begin
                    if(PowerDown == 2'b00)
					begin
						c_state		<= P0;
					end
					else if(PowerDown == 2'b01)
					begin
						c_state		<= P1;
					end
					else if(PowerDown == 2'b10)
					begin
						c_state		<= P2;
					end
					else if(PowerDown == 2'b11)
					begin
						c_state		<= P3;
					end
                end
                else 
                begin
                    c_state    <=  RX_EQ;	
                end
            end

            IDLE : 
            begin
                if(PowerDown == 2'b00)
				begin
					c_state		<= P0;
				end
				else if(PowerDown == 2'b01)
				begin
					c_state		<= P1;
				end
				else if(PowerDown == 2'b10)
				begin
					c_state		<= P2;
				end
				else if(PowerDown == 2'b11)
				begin
					c_state		<= P3;
				end
            end

            default : c_state    <=  IDLE;	
        endcase
    end
end

endmodule

`ifdef MSIM
module datapath
`else
module `getname( datapath,`module_name)
`endif
#(
    parameter	LGPKTGATE=4,
    parameter	LGCDCRAM = 5,
    parameter [0:0]	OPT_SCRAMBLER=1,
    parameter [0:0]	OPT_LITTLE_ENDIAN=0,
    parameter [0:0]	OPT_INVERT_TX = 1'b0,
    localparam	RAWDW =  64,//32
    localparam	LCLDW =  64,
    localparam	PKTDW = 64//128
) (
    input	wire		i_rx_clk, i_tx_clk, i_reset_n,
    input	wire		i_sys_clk, i_fast_clk,
    
    input	wire				i_raw_data_valid,
    input	wire	[RAWDW-1:0]	i_raw_data,
    output	reg	[RAWDW-1:0]	o_raw_data,
    
    input	wire				S_VALID,
    output	wire				S_READY,
    input	wire	[PKTDW-1:0]		S_DATA,
    input	wire	[3:0]		S_SYNCHEAD,
    input	wire				S_STARTBLOCK,
    
    output	wire				M_VALID,
    input	wire				M_READY,
    output	wire	[PKTDW-1:0]		M_DATA,
    output	wire	[3:0]		M_SYNCHEAD,
    output	wire				M_STARTBLOCK
);


reg		rx_reset_n, tx_reset_n, fast_reset_n;
reg	[1:0]	rx_reset_pipe, tx_reset_pipe, fast_reset_pipe;

wire			scramble_data_ready;
wire			scramble_data_valid;
wire			scramble_data_block_start;
wire	[63:0]	scramble_data;
wire	[3:0]	scramble_data_block_head;
wire			dc_data_ready;
wire			dc_data_valid;
wire			dc_data_block_start;
wire	[63:0]	dc_data;
wire	[3:0]	dc_data_block_head;

wire		rx132b_valid;
wire		rx132b_startblock;
wire	[65:0]	rx132b_data;

wire		tx132b_ready;
wire	[65:0]	tx132b_data;

wire		rx_valid, rx_ready, rx_startblock;
wire	[65:0]	rx_data;

wire		SRC_VALID, SRC_READY, SRC_LAST, SRC_ABORT;
wire	[LCLDW-1:0]	SRC_DATA;
wire	[(LCLDW/8)-1:0]	SRC_DATAK;
wire	SRC_STARTBLOCK;
wire	[3:0] SRC_BLOCKHEAD;

wire		tx_ready, tx_valid, ign_tx_high, ign_rx_high;
wire	[65:0]	tx_data;

wire		RXWD_VALID, RXWD_READY, RXWD_LAST, RXWD_ABORT;
wire	[PKTDW-1:0]	RXWD_DATA;
wire	[(PKTDW/8)-1:0]	RXWD_DATAK;
wire	[PKTDW-1:0]	unswapped_m_data;

wire		rx_fast_ready, rx_fast_valid, rx_fast_empty,
        ign_rx132b_full;
wire	[65:0]	rx_fast_data;
wire	rx_fast_startblock;

wire	[LCLDW-1:0]	tx128b_data;

always @(posedge i_fast_clk or negedge i_reset_n)
if (!i_reset_n)
    { fast_reset_n, fast_reset_pipe } <= 0;
else
    { fast_reset_n, fast_reset_pipe } <= { fast_reset_pipe, i_reset_n };

always @(posedge i_rx_clk or negedge i_reset_n)
if (!i_reset_n)
    { rx_reset_n, rx_reset_pipe } <= 0;
else
    { rx_reset_n, rx_reset_pipe } <= { rx_reset_pipe, i_reset_n };

always @(posedge i_tx_clk or negedge i_reset_n)
if (!i_reset_n)
    { tx_reset_n, tx_reset_pipe } <= 0;
else
    { tx_reset_n, tx_reset_pipe } <= { tx_reset_pipe, i_reset_n };
    
`ifdef MSIM
p132brxgears u_p132brxgears
`else
`getname(p132brxgears,`module_name) u_p132brxgears
`endif
(
    .i_clk(i_rx_clk), 
    .i_reset(!rx_reset_n),
    .i_data_valid(i_raw_data_valid),
    .i_data(i_raw_data),
    .M_VALID(rx132b_valid),
    .M_STARTBLOCK(rx132b_startblock),
    .M_DATA( rx132b_data)
);

`ifdef MSIM
async_fifo
`else
`getname(async_fifo,`module_name)
`endif
#(
    .DSIZE 			(67), //parameter             = 40,
    .ASIZE 			(5), //parameter             = 10,
    .AEMPT 			(1), //parameter             = 1,
    .AFULL 			(31)  //parameter             = 32
)
u_rx_async_fifo
(
    .Q				({rx_fast_startblock, rx_fast_data}), //output reg [DSIZE-1:0]   	
    .Full			(), //output reg               	
    .Empty			(rx_fast_empty), //output reg               	
    .AlmostEmpty	(), //output reg               	
    .AlmostFull		(), //output reg               	
    .RdDataNum		(), //output reg [ASIZE:0]   	
    .WrDataNum		(), //output reg [ASIZE:0]   	
    .Data			({rx132b_startblock, rx132b_data}), //input   [DSIZE-1:0]   	
    .WrEn			(rx132b_valid), //input                 	
    .WrClock		(i_rx_clk), //input                 	            	
    .WPReset		(~rx_reset_n), //input                 	
    .RdEn			(rx_fast_ready), //input                 	
    .RdClock		(i_fast_clk), //input                 	
    .RPReset		(~fast_reset_n)  //input                 	
);
assign	rx_fast_valid = !rx_fast_empty;


assign rx_data = rx_fast_data;
assign rx_valid = rx_fast_valid;
assign rx_startblock = rx_fast_startblock;
assign rx_fast_ready = rx_ready;

`ifdef MSIM
p1284pkt u_p1284pkt
`else
`getname(p1284pkt,`module_name) u_p1284pkt
`endif
(
    .TX_CLK				(i_fast_clk),// input	wire			 
    .S_ARESETN			(fast_reset_n),// input	wire			
    .M_VALID			(SRC_VALID),// output	wire			
    .M_DATA				(SRC_DATA),// output	wire	[63:0]	
    .M_SYNCHEAD			(SRC_BLOCKHEAD),// output	wire	[3:0]	
    .M_STARTBLOCK		(SRC_STARTBLOCK),// output	wire			
    .TXREADY			(SRC_READY),// output	wire			
    .TXDATA_VALID		(rx_valid),// input   wire			
    .TXDATA_STARTBLOCK	(rx_startblock),// input   wire			
    .TXDATA				(rx_data)// input	wire	[65:0]	
);

assign	rx_ready = 1'b1;

`ifdef MSIM
usb3_1_descramble u_usb3_1_descramble
`else
`getname(usb3_1_descramble,`module_name) u_usb3_1_descramble
`endif
(
    .clk					(i_fast_clk),//input wire 			
    .rstn					(fast_reset_n),//input wire 			
    .descramble_en			(1'b1),//input wire 			
    .data_in_valid			(SRC_VALID),//input wire 			
    .data_in_start_block	(SRC_STARTBLOCK),//input wire 			
    .data_in_block_head		(SRC_BLOCKHEAD),//input wire [3:0] 	
    .data_in				(SRC_DATA),//input wire [63:0] 	
    .data_out_valid			(M_VALID),//output wire 		
    .data_out_start_block	(M_STARTBLOCK),//output wire 		
    .data_out_block_head	(M_SYNCHEAD),//output wire [3:0] 	
    .data_out				(M_DATA)//output wire [63:0] 	
);


`ifdef MSIM
usb3_1_scramble u_usb3_1_scramble
`else
`getname(usb3_1_scramble,`module_name) u_usb3_1_scramble
`endif
(
.clk					(i_fast_clk),//input 				
.rst					(~fast_reset_n),//input 				
.data_in_ready			(S_READY),
.data_in_valid			(S_VALID),//input 				
.data_in_start_block	(S_STARTBLOCK),//input 				
.data_in_block_head		(S_SYNCHEAD),//input [3:0] 		
.data_in				(S_DATA),//input [63:0] 				
.data_out_ready			(scramble_data_ready),
.data_out_valid			(scramble_data_valid),//output reg 			
.data_out_start_block	(scramble_data_block_start),//output reg 			
.data_out_block_head	(scramble_data_block_head),//output reg [3:0] 	
.data_out				(scramble_data) //output reg [63:0] 	
);

// assign S_READY = scramble_data_ready;
// assign scramble_data_valid = S_VALID;
// assign scramble_data_block_start = S_STARTBLOCK;
// assign scramble_data_block_head = S_SYNCHEAD;
// assign scramble_data = S_DATA;

`ifdef MSIM
dc_balance u_dc_balance
`else
`getname(dc_balance,`module_name) u_dc_balance
`endif
(
.clk					(i_fast_clk),  //input                      
.rst					(!fast_reset_n),  //input                      
.data_in_ready			(scramble_data_ready),  //output                
.data_in_valid			(scramble_data_valid),  //input               
.data_in_block_start	(scramble_data_block_start),  //input              
.data_in_block_head		(scramble_data_block_head),  //input  [3:0]        
.data_in				(scramble_data),  //input  [63:0]        
.data_out_ready			(dc_data_ready),  //input                    
.data_out_valid			(dc_data_valid),  //output                    
.data_out_block_start	(dc_data_block_start),  //output                  
.data_out_block_head	(dc_data_block_head),  //output [3:0]             
.data_out				(dc_data)   //output [63:0]                  
);

`ifdef MSIM
pkt4p128b_v2 u_pkt4p128b
`else
`getname(pkt4p128b_v2,`module_name) u_pkt4p128b
`endif
(
    .TX_CLK(i_fast_clk), 
    .S_ARESETN(fast_reset_n),
    
    .S_VALID(dc_data_valid),
    .S_READY(dc_data_ready),
    .S_DATA(dc_data),
    .S_SYNCHEAD(dc_data_block_head),
    .S_STARTBLOCK(dc_data_block_start),
    
    .TXREADY(tx_ready),
    .TXDATA_VALID(tx_valid),
    .TXDATA(tx_data)
);

assign tx132b_data = tx_data;
assign tx_ready = tx132b_ready;

`ifdef MSIM
p132btxgears u_p132btxgears
`else
`getname(p132btxgears,`module_name) u_p132btxgears
`endif
(
    .i_clk(i_fast_clk), .i_reset(!fast_reset_n),
    .S_READY(tx132b_ready),
    .S_VALID(tx_valid),
    .S_DATA( tx132b_data),
    .i_ready(1'b1),
    .o_data(tx128b_data)
);

always @(posedge i_fast_clk)
    o_raw_data <=   tx128b_data;


function automatic [PKTDW-1:0] SWAP_ENDIAN_PKT(input [PKTDW-1:0] in);
    integer	ib;
    reg	[PKTDW-1:0]	r;
begin
    r = 0;
    for(ib=0; ib<PKTDW; ib=ib+8)
        r[ib +: 8] = in[PKTDW-8-ib +: 8];
    SWAP_ENDIAN_PKT = r;
end endfunction

endmodule



`ifdef MSIM
module p132brxgears
`else
module `getname( p132brxgears,`module_name)
`endif
(
    input	wire	i_clk, i_reset,

    input	wire			i_data_valid,
    input	wire	[63:0]	i_data,
    output	reg				M_VALID,
    output	reg				M_STARTBLOCK,
    output	reg		[65:0]	M_DATA
);
localparam	LOCKMSB = 6;
reg		rx_valid, rx_valid_r0, rx_valid_r1, rx_valid_r2, rx_valid_r3, rx_valid_r4;
reg	[7:0]	rx_count;
reg	rx_count_high, rx_count_low;
reg	[7:0]	rx_count_r;
reg	[131:0]	rx_gears;

reg	[65:0]	al_last, al_last_r;
reg	[131:0]	al_data;
wire [263:0]	al_data_all;
reg	[65:0]	ign_al_msb;
reg	[7:0]	al_shift;
reg	[3:0]	al_cnt;
reg	[2:0]	al_flag;
reg	[LOCKMSB:0]	lock_count;
reg	lock_count_msb;
reg	[8:0]	blockhead_cnt_0;
reg	[8:0]	blockhead_cnt_1;

reg	[255:0]	full_set;
reg	[63:0]	r_data;
reg	[63:0]	r_data_r;
reg		i_data_valid_r;

reg [1:0] state;

localparam	st_idle = 2'd0;
localparam	st_rx = 2'd1;
localparam	st_head = 2'd2;

always @(posedge i_clk) begin
    i_data_valid_r <= i_data_valid;
    if(i_data_valid)
        r_data <= i_data;
end

always @(posedge i_clk)
begin
    if (i_reset)
    begin
        rx_count <= 0;
        rx_count_r <= 0;
        r_data_r <= 0;
        rx_valid <= 0;
        rx_valid_r0 <= 0;
        rx_valid_r1 <= 0;
        rx_valid_r2 <= 0;
        rx_valid_r3 <= 0;
        rx_valid_r4 <= 0;
    end else begin
        if(i_data_valid)
            r_data_r <= r_data;
        if(i_data_valid_r) begin
            if (rx_valid)
            begin
                rx_count <= rx_count + 64 - 66;
            end else begin
                rx_count <= rx_count + 64;
            end
            rx_count_r <= rx_count;
            rx_count_high <= (rx_count >= 67);
            rx_count_low <= (rx_count >= 67);
            rx_valid <= (rx_count >= 67);
            rx_valid_r0 <= rx_valid;
            rx_valid_r1 <= rx_valid_r0;
            rx_valid_r2 <= rx_valid_r1;
            rx_valid_r3 <= rx_valid_r2;
            rx_valid_r4 <= rx_valid_r3;
        end
        else begin
            rx_valid <= 0;
        end
    end
end

always @(posedge i_clk)
begin
    if (i_reset) begin
        full_set <= 0;
    end
    else
        if(rx_valid)
            full_set <= (full_set | ({ r_data_r, 192'h0} >> rx_count)) << 66;
        else
            full_set <= (full_set | ({ r_data_r, 192'h0} >> rx_count));
end

always @(full_set) begin
    rx_gears <= full_set[255:124];
end

always @(posedge i_clk)
if (i_reset) begin
    al_last <= 0;
    al_last_r <= 0;
end
else begin
    al_last <= rx_gears[131:66];
    al_last_r <= al_last;
end

wire [197:0] test;
assign test = {al_last, rx_gears};
assign al_data_all = {al_last_r, al_last, rx_gears} << al_shift;
always @(posedge i_clk)
if (rx_valid_r1)
    al_data <= al_data_all[263:132];

always @(posedge i_clk)
if (i_reset)
begin
    lock_count <= 0;
    al_cnt <= 0;
    al_shift <= 0;
    al_flag <= 0;
    blockhead_cnt_0 <= 0;
    blockhead_cnt_1 <= 0;
    state <= st_idle;
end else if (rx_valid_r1)
begin
    case(state)
        st_idle : begin
            if((al_data[131:128] == 4'b0011 || al_data[131:128] == 4'b1100)) begin
                state <= st_rx;
                al_flag <= 0;
            end
            else begin
                if(al_flag == 3) begin
                    al_flag <= 0;
                    if(al_shift <= 132)
                        al_shift <= al_shift + 1'b1;
                    else
                        al_shift <= 0;
                end
                else begin
                    al_flag <= al_flag + 1'b1;
                end
            end
        end

        st_rx : begin
            state <= st_head;
        end

        st_head : begin
            if(al_flag == 0) begin
                al_flag <= al_flag + 1'b1;
                if ((al_data[131:128] == 4'b0011 || al_data[131:128] == 4'b1100)) begin
                    al_cnt <= 4'b0001;
                end
            end
            else if(al_flag == 1) begin
                al_flag <= al_flag + 1'b1;
                if ((al_data[131:128] == 4'b0011 || al_data[131:128] == 4'b1100)) begin
                    al_cnt[1] <= 1;
                end
            end
            else if(al_flag == 2) begin
                al_flag <= al_flag + 1'b1;
                if ((al_data[131:128] == 4'b0011 || al_data[131:128] == 4'b1100)) begin
                    al_cnt[2] <= 1;
                end
            end
            else if(al_flag == 3) begin
                al_flag <= al_flag + 1'b1;
                if ((al_data[131:128] == 4'b0011 || al_data[131:128] == 4'b1100)) begin
                    al_cnt[3] <= 1;
                end
            end
            else if(al_flag == 4) begin
                al_flag <= al_flag + 1'b1;
            end
            else if(al_flag == 5) begin
                al_flag <= al_flag + 1'b1;
            end
            else if(al_flag == 6) begin
                al_flag <= al_flag + 1'b1;
            end
            else if(al_flag == 7) begin
                al_flag <= 0;
                al_cnt <= 0;
                state <= st_idle;
                if(al_cnt[0] && al_cnt[2]) begin
                    if(!lock_count[LOCKMSB])
                        lock_count <= lock_count + 1;
                    if(!blockhead_cnt_0[8])
                        blockhead_cnt_0 <= blockhead_cnt_0 + 1'b1;
                    if(blockhead_cnt_1 > 0)
                        blockhead_cnt_1 <= blockhead_cnt_1 - 1'b1;
                end
                else if(al_cnt[1] && al_cnt[3]) begin
                    if(!lock_count[LOCKMSB])
                        lock_count <= lock_count + 1;
                    if(!blockhead_cnt_1[8])
                        blockhead_cnt_1 <= blockhead_cnt_1 + 1'b1;
                    if(blockhead_cnt_0 > 0)
                        blockhead_cnt_0 <= blockhead_cnt_0 - 1'b1;
                end
                else begin
                    blockhead_cnt_0 <= 0;
                    blockhead_cnt_1 <= 0;
                    if(al_shift <= 132)
                        al_shift <= al_shift + 1'b1;
                    else
                        al_shift <= 0;

                    if (lock_count > 3) begin
                        lock_count <= lock_count - 4;
                    end
                    else begin
                        lock_count <= 0;
                    end
                end
            end
        end

        default : state <= st_idle;
    endcase
end

always@(posedge i_clk) begin
    if (i_reset) begin
        lock_count_msb <= 0;
        M_VALID <= 0;
        M_DATA <= 0;
        M_STARTBLOCK <= 0;
    end
    else begin
        M_VALID <= rx_valid_r1 && lock_count[LOCKMSB];
        M_DATA  <= rx_valid_r1? al_data[131:66] : 0;
        lock_count_msb <= lock_count[LOCKMSB];
        if(!lock_count_msb && lock_count[LOCKMSB]) begin
            if(blockhead_cnt_0 > blockhead_cnt_1)
                M_STARTBLOCK <= 1'b1;
            else
                M_STARTBLOCK <= 1'b0;
        end
        else if(lock_count[LOCKMSB]) begin
            M_STARTBLOCK <= ~M_STARTBLOCK;
        end
        else begin
            M_STARTBLOCK <= 1'b0;
        end
    end
end

endmodule

`ifdef MSIM
module p1284pkt
`else
module `getname( p1284pkt,`module_name)
`endif
(
	input	wire			TX_CLK, 
	input	wire			S_ARESETN,

	output	wire			M_VALID,
	output	wire	[63:0]	M_DATA,
	output	wire	[3:0]	M_SYNCHEAD,
	output	wire			M_STARTBLOCK,

	output	wire			TXREADY,
	input   wire			TXDATA_VALID,
	input   wire			TXDATA_STARTBLOCK,
	input	wire	[65:0]	TXDATA
);

reg			M_VALID_r;
reg	[63:0]	M_DATA_r;
reg	[3:0]	M_SYNCHEAD_r;
reg			M_STARTBLOCK_r;


reg	[65:0]	data_r;
reg			data_valid_r;
reg			data_startblock_r;
reg	[3:0]	head_r;
reg			head;

assign TXREADY = S_ARESETN? 1'b1 : 1'b0;
assign M_VALID = M_VALID_r;
assign M_DATA = M_DATA_r;
assign M_SYNCHEAD = M_SYNCHEAD_r;
assign M_STARTBLOCK = M_STARTBLOCK_r;

always@(posedge TX_CLK or negedge S_ARESETN) begin
	if(!S_ARESETN) begin
		M_VALID_r <= 0;
		M_DATA_r <= 0;
		M_SYNCHEAD_r <= 0;
		M_STARTBLOCK_r <= 0;
		data_r <= 0;
		data_valid_r <= 0;
		data_startblock_r <= 0;
		head_r <= 0;
		head <= 0;
	end
	else begin
		data_valid_r <= TXDATA_VALID;
		if(TXDATA_VALID) begin
			data_r <= TXDATA;
			data_startblock_r <= TXDATA_STARTBLOCK;
		end
		if(TXDATA_STARTBLOCK && TXDATA_VALID) begin
			head <= 1'b1;
		end
		if(TXDATA_STARTBLOCK && TXDATA_VALID) begin
			head_r <= TXDATA[65:62];
		end
		
		M_SYNCHEAD_r <= head_r;
		if(head && data_valid_r && !data_startblock_r) begin
			M_VALID_r <= 1;
			M_DATA_r <= data_r[63:0];
			M_STARTBLOCK_r <= 0;
		end
		else if(head && data_valid_r && data_startblock_r) begin
			M_VALID_r <= 1;
			M_DATA_r <= {data_r[61:0], TXDATA[65:64]};
			M_STARTBLOCK_r <= 1;
		end
		else begin
			M_VALID_r <= 0;
			M_DATA_r <= 0;
			M_STARTBLOCK_r <= 0;
		end
	end
end
		
endmodule


`ifdef MSIM
module usb3_1_descramble
`else
module `getname( usb3_1_descramble,`module_name)
`endif
(
    input wire clk,
    input wire rstn,

    input wire descramble_en,
    input wire data_in_valid,
    input wire data_in_start_block,
    input wire [3:0] data_in_block_head,
    input wire [63:0] data_in,

    output reg data_out_valid,
    output reg data_out_start_block,
    output reg [3:0] data_out_block_head,
    output reg [63:0] data_out
  );


localparam SKP              = 8'hCC;
localparam SKPEND           = 8'h33;
localparam SYNC_LOW         = 8'h00;
localparam SYNC_HIG         = 8'hFF;
localparam ENDS             = 8'h65;
localparam DPHPS            = 8'h95;
localparam EDBS             = 8'h69;
localparam SHPS             = 8'h9A;
localparam SDPS             = 8'h96;
localparam SLCS             = 8'h4B;
localparam EPFS             = 8'h36;
localparam LIS              = 8'h5A;
localparam SDS              = 8'hE1;
localparam TS1              = 8'h1E;
localparam TS2              = 8'h2D;
localparam TSEQ             = 8'h87;
localparam BLOCK_CONTROL    = 4'hC;
localparam BLOCK_DATA       = 4'h3;

reg scram_rst;
reg scram_en;
reg [2:0] scram_xor;
reg [2:0] scram_xor_r;
reg [7:0] block_type;
wire [63:0] data_out_c;
reg  [63:0] data_out_c_r;


reg data_out_valid_r;
reg data_out_start_block_r;
reg [3:0] data_out_block_head_r;
reg [63:0] data_out_r;
// wire dc_balance;

always@(posedge clk or negedge rstn) begin
    if(!rstn) begin
        scram_rst <= 0;
        scram_en <= 0;
        block_type <= 0;
        scram_xor <= 0;
    end
    else begin
        if(data_in_valid) begin
            scram_rst <= 0;
            if(!data_in_start_block) begin
                if(data_in_block_head == BLOCK_CONTROL) begin
                    case(block_type)
                        SDS : begin
                            scram_en <= 1;
                            scram_xor <= 3'b000;
                        end

                        SKP, SKPEND : begin
                            scram_en <= 0;
                            scram_xor <= 3'b000;
                        end

                        TS1, TS2, TSEQ : begin
                            scram_en <= 1;
                            // if(dc_balance)
                            //     scram_xor <= 3'b110;
                            // else
                                scram_xor <= 3'b111;
                        end

                        SYNC_HIG, SYNC_LOW : begin
                            scram_rst <= 1;
                            scram_xor <= 3'b000;
                        end

                        default : begin
                            scram_en <= 1;
                            scram_xor <= 3'b111;
                        end
                    endcase
                end
                else begin
                    scram_en <= 1;
                    scram_xor <= 3'b111;
                end
            end
            else if(data_in_block_head == BLOCK_DATA) begin
                block_type <= data_in[63:56];
                scram_en <= 1;
                scram_xor <= 3'b111;
            end
            else begin
                block_type <= data_in[63:56];
                case(data_in[63:56])
                    SDS : begin
                        scram_en <= 1;
                        scram_xor <= 3'b000;
                    end

                    SKP, SKPEND : begin
                        scram_en <= 0;
                        scram_xor <= 3'b000;
                    end

                    SYNC_HIG, SYNC_LOW : begin
                        scram_rst <= 1;
                        scram_xor <= 3'b000;
                    end

                    default : begin
                        scram_en <= 1;
                        scram_xor <= 3'b011;
                    end
                endcase
            end
        end
        else begin
            scram_rst <= 0;
            scram_en <= 0;
            scram_xor <= scram_xor;
        end
    end
end

always@(posedge clk or negedge rstn) begin
    if(!rstn) begin
        data_out_valid_r        <= 0;
        data_out_start_block_r  <= 0;
        data_out_block_head_r   <= 0;
        data_out_r              <= 0;
        data_out_c_r            <= 0;
    end
    else begin
        data_out_valid_r        <= data_in_valid;
        data_out_start_block_r  <= data_in_start_block;
        data_out_block_head_r   <= data_in_block_head;
        data_out_r              <= data_in;
        // if(data_in_valid) begin
            data_out_c_r            <= data_out_c;
        // end
    end
end

always@(posedge clk or negedge rstn) begin
    if(!rstn) begin
        data_out_valid          <= 0;
        data_out_start_block    <= 0;
        data_out_block_head     <= 0;
        data_out                <= 0;
    end
    else begin
        if(data_out_valid_r) begin
            data_out_valid          <= data_out_valid_r;
            data_out_start_block    <= data_out_start_block_r;
            data_out_block_head     <= data_out_block_head_r;
            if(scram_xor[2])
                data_out[63:56]         <= data_out_r[63:56] ^ data_out_c[63:56];
            else
                data_out[63:56]         <= data_out_r[63:56];

            if(scram_xor[1])
                data_out[55:16]         <= data_out_r[55:16] ^ data_out_c[55:16];
            else
                data_out[55:16]         <= data_out_r[55:16];

            if(scram_xor[0])
                data_out[15:0]          <= data_out_r[15:0] ^ data_out_c[15:0];
            else
                data_out[15:0]          <= data_out_r[15:0];
        end
        else begin
            data_out_valid          <= 0;
            data_out_start_block    <= 0;
            data_out_block_head     <= 0;
            data_out                <= 0;
        end
    end
end


`ifdef MSIM
usb3_1_lfsr Inst_usb3_1_lfsr
`else
`getname(usb3_1_lfsr,`module_name) Inst_usb3_1_lfsr
`endif
(
    .clk                (clk),//input               
    .rst                (!rstn),//input               
    .scram_rst          (scram_rst),//input               
    .scram_init         (23'h1DBFBC),//input	[22:0]      
    .scram_en           (scram_en),//input               
    .data_in            (64'h0),//input [63:0]        
    .data_out_c         (data_out_c),//output reg [63:0]   
    .data_out           () //output reg [63:0]   
);

endmodule


`ifdef MSIM
module usb3_1_scramble
`else
module `getname( usb3_1_scramble,`module_name)
`endif
(
    input wire clk,
    input wire rst,

    output wire data_in_ready,
    input wire data_in_valid,
    input wire data_in_start_block,
    input wire [3:0] data_in_block_head,
    input wire [63:0] data_in,

    input wire data_out_ready,
    output reg data_out_valid,
    output reg data_out_start_block,
    output reg [3:0] data_out_block_head,
    output reg [63:0] data_out


);

localparam SKP              = 8'hCC;
localparam SKPEND           = 8'h33;
localparam SYNC_LOW         = 8'h00;
localparam SYNC_HIG         = 8'hFF;
localparam ENDS             = 8'h65;
localparam DPHPS            = 8'h95;
localparam EDBS             = 8'h69;
localparam SHPS             = 8'h9A;
localparam SDPS             = 8'h96;
localparam SLCS             = 8'h4B;
localparam EPFS             = 8'h36;
localparam LIS              = 8'h5A;
localparam SDS              = 8'hE1;
localparam TS1              = 8'h1E;
localparam TS2              = 8'h2D;
localparam TSEQ             = 8'h87;
localparam BLOCK_CONTROL    = 4'hC;
localparam BLOCK_DATA       = 4'h3;

reg scram_rst;
reg scram_en;
reg [2:0] scram_xor;
reg [2:0] scram_xor_r;
reg [7:0] block_type;
wire [63:0] data_out_c;
reg  [63:0] data_out_c_r;


reg data_out_valid_r;
reg data_out_start_block_r;
reg [3:0] data_out_block_head_r;
reg [63:0] data_out_r;
// wire dc_balance;

assign data_in_ready = data_out_ready;

always@(posedge clk or posedge rst) begin
    if(rst) begin
        scram_rst <= 0;
        scram_en <= 0;
        block_type <= 0;
        scram_xor <= 0;
    end
    else begin
        if(data_in_valid && data_out_ready) begin
            scram_rst <= 0;
            if(!data_in_start_block) begin
                case(block_type)
                    SDS : begin
                        scram_en <= 1;
                        scram_xor <= 3'b000;
                    end

                    SKP, SKPEND : begin
                        scram_en <= 0;
                        scram_xor <= 3'b000;
                    end

                    TS1, TS2, TSEQ : begin
                        scram_en <= 1;
                        // if(dc_balance)
                        //     scram_xor <= 3'b110;
                        // else
                            scram_xor <= 3'b111;
                    end

                    SYNC_HIG, SYNC_LOW : begin
                        scram_rst <= 1;
                        scram_xor <= 3'b000;
                    end

                    default : begin
                        scram_en <= 1;
                        scram_xor <= 3'b111;
                    end
                endcase
            end
            else if(data_in_block_head == BLOCK_DATA) begin
                block_type <= data_in[63:56];
                scram_en <= 1;
                scram_xor <= 3'b111;
            end
            else if(data_in_block_head == BLOCK_CONTROL) begin
                block_type <= data_in[63:56];
                case(data_in[63:56])
                    SDS : begin
                        scram_en <= 1;
                        scram_xor <= 3'b000;
                    end

                    SKP, SKPEND : begin
                        scram_en <= 0;
                        scram_xor <= 3'b000;
                    end

                    SYNC_HIG, SYNC_LOW : begin
                        scram_rst <= 1;
                        scram_xor <= 3'b000;
                    end

                    default : begin
                        scram_en <= 1;
                        scram_xor <= 3'b011;
                    end
                endcase
            end
        end
        else begin
            scram_rst <= 0;
            scram_en <= 0;
            scram_xor <= scram_xor;
        end
    end
end

always@(posedge clk or posedge rst) begin
    if(rst) begin
        data_out_valid_r        <= 0;
        data_out_start_block_r  <= 0;
        data_out_block_head_r   <= 0;
        data_out_r              <= 0;
        data_out_c_r            <= 0;
    end
    else begin
        data_out_valid_r        <= data_in_valid;
        if(data_in_valid && data_out_ready) begin
            data_out_start_block_r  <= data_in_start_block;
            data_out_block_head_r   <= data_in_block_head;
            data_out_r              <= data_in;
        end
        if(scram_en) begin
            data_out_c_r            <= data_out_c;
        end
    end
end

always@(posedge clk or posedge rst) begin
    if(rst) begin
        data_out_valid          <= 0;
        data_out_start_block    <= 0;
        data_out_block_head     <= 0;
        data_out                <= 0;
    end
    else begin
        data_out_valid          <= data_out_valid_r;
        if(data_out_valid_r && data_out_ready) begin
            data_out_start_block    <= data_out_start_block_r;
            data_out_block_head     <= data_out_block_head_r;
            if(scram_en) begin
                if(scram_xor[2])
                    data_out[63:56]         <= data_out_r[63:56] ^ data_out_c[63:56];
                else
                    data_out[63:56]         <= data_out_r[63:56];

                if(scram_xor[1])
                    data_out[55:16]         <= data_out_r[55:16] ^ data_out_c[55:16];
                else
                    data_out[55:16]         <= data_out_r[55:16];

                if(scram_xor[0])
                    data_out[15:0]          <= data_out_r[15:0] ^ data_out_c[15:0];
                else
                    data_out[15:0]          <= data_out_r[15:0];
            end
            else begin
                if(scram_xor[2])
                    data_out[63:56]         <= data_out_r[63:56] ^ data_out_c_r[63:56];
                else
                    data_out[63:56]         <= data_out_r[63:56];

                if(scram_xor[1])
                    data_out[55:16]         <= data_out_r[55:16] ^ data_out_c_r[55:16];
                else
                    data_out[55:16]         <= data_out_r[55:16];

                if(scram_xor[0])
                    data_out[15:0]          <= data_out_r[15:0] ^ data_out_c_r[15:0];
                else
                    data_out[15:0]          <= data_out_r[15:0];
            end
        end
    end
end

// assign data_out_c = 0;
`ifdef MSIM
usb3_1_lfsr Inst_usb3_1_lfsr
`else
`getname(usb3_1_lfsr,`module_name) Inst_usb3_1_lfsr
`endif
(
    .clk                (clk),//input               
    .rst                (rst),//input               
    .scram_rst          (scram_rst),//input               
    .scram_init         (23'h1DBFBC),//input	[22:0]      
    .scram_en           (scram_en),//input               
    .data_in            (64'h0),//input [63:0]        
    .data_out_c         (data_out_c),//output reg [63:0]   
    .data_out           () //output reg [63:0]   
);

endmodule // scrambler


`ifdef MSIM
module dc_balance
`else
module `getname( dc_balance,`module_name)
`endif
(
    input  wire         clk,             
    input  wire         rst,             
    output wire         data_in_ready,      
    input  wire         data_in_valid,      
    input  wire         data_in_block_start,     
    input  wire [3:0]   data_in_block_head,      
    input  wire [63:0]  data_in,         
    
    input  wire         data_out_ready,      
    output wire         data_out_valid,            
    output wire         data_out_block_start,          
    output wire [3:0]   data_out_block_head,           
    output wire [63:0]  data_out                  
);

localparam SKP              = 8'hCC;
localparam SKPEND           = 8'h33;
localparam SYNC_LOW         = 8'h00;
localparam SYNC_HIG         = 8'hFF;
localparam ENDS             = 8'h65;
localparam DPHPS            = 8'h95;
localparam EDBS             = 8'h69;
localparam SHPS             = 8'h9A;
localparam SDPS             = 8'h96;
localparam SLCS             = 8'h4B;
localparam EPFS             = 8'h36;
localparam LIS              = 8'h5A;
localparam SDS              = 8'hE1;
localparam TS1              = 8'h1E;
localparam TS2              = 8'h2D;
localparam TSEQ             = 8'h87;
localparam BLOCK_CONTROL    = 4'hC;
localparam BLOCK_DATA       = 4'h3;

localparam DC_CNT_NORMAL    = 11'd1024;
localparam DC_CNT_MAX       = DC_CNT_NORMAL + 11'd511;      
localparam DC_CNT_MIN       = DC_CNT_NORMAL - 11'd511;      
localparam DC_CNT_1_15      = DC_CNT_NORMAL + 11'd15;
localparam DC_CNT_1_31      = DC_CNT_NORMAL + 11'd31;
localparam DC_CNT_0_15      = DC_CNT_NORMAL - 11'd15;
localparam DC_CNT_0_31      = DC_CNT_NORMAL - 11'd31;

reg             data_valid_r;               
reg             data_block_start_r;         
reg     [3:0]   data_block_head_r;          
reg     [63:0]  data_r;               
reg     [10:0]  dc_cnt;                     
wire    [10:0]  dc_cnt_next;                
reg     [6:0]   cnt_1;                      
reg     [6:0]   cnt_0;          
reg             dc_replace_en_r;            
reg             sds_detect_r;      
reg     [7:0]   dc_en_byte_6;               
reg     [7:0]   dc_en_byte_7;              
wire    [63:0]  data_out_rr;                
reg             data_valid_out_r;           
reg             start_block_out_r;          
reg     [3:0]   block_type_out_r;           
reg     [63:0]  data_out_r;                 


assign data_in_ready = data_out_ready;
assign data_out_valid = data_valid_out_r;
assign data_out_block_start = start_block_out_r;
assign data_out_block_head = block_type_out_r;
assign data_out = data_out_r;
assign data_out_rr = {dc_en_byte_7, dc_en_byte_6, data_r[47:0]};

// always @(posedge clk or posedge rst) begin
//     if (rst) begin
//         data_valid_r <= 1'b0;
//         data_block_start_r <= 1'b0;
//         data_block_head_r <= 4'b1100;
//         data_r <= {64{1'b0}};
//     end
//     else begin
//         data_valid_r <= data_in_valid;
//         data_block_start_r <= data_in_block_start;
//         data_block_head_r <= data_in_block_head;
//         data_r <= data_in;
//     end
// end

always @(*) begin
    data_valid_r = data_in_valid;
    data_block_start_r = data_in_block_start;
    data_block_head_r = data_in_block_head;
    data_r = data_in;
end

always @(posedge clk or posedge rst) begin
    if (rst) begin
        data_valid_out_r <= 1'b0;
        start_block_out_r <= 1'b0;
        block_type_out_r <= 4'b1100;
        data_out_r <= {64{1'b0}};
    end
    else begin
        if (data_out_ready) begin
            data_valid_out_r <= data_valid_r;
            start_block_out_r <= data_block_start_r;
            block_type_out_r <= data_block_head_r;
            data_out_r <= data_out_rr;
        end
    end
end


always @(posedge clk or posedge rst) begin
    if (rst)
    begin
        dc_cnt <= DC_CNT_NORMAL; 
    end
    else begin
        if (data_valid_r && ((data_r[7:0] != TS1) && (data_r[7:0] != TS2) && (data_r[7:0] != TSEQ))) begin
            dc_cnt <= DC_CNT_NORMAL; 
        end
        else begin
            if (data_valid_r == 1'b1 && data_out_ready) begin
                if (sds_detect_r == 1'b1) begin
                    dc_cnt <= DC_CNT_NORMAL; 
                end
                else begin
                    if (dc_cnt_next > DC_CNT_MAX) begin
                        dc_cnt <= DC_CNT_MAX;
                    end
                    else begin
                        if (dc_cnt_next < DC_CNT_MIN) begin
                            dc_cnt <= DC_CNT_MIN;
                        end
                        else begin
                            dc_cnt <= dc_cnt_next; 
                        end
                    end
                end
            end
        end
    end
end

assign dc_cnt_next = dc_cnt + cnt_1 - cnt_0;  

always@(*) begin : process_0
    integer i;
    cnt_1 = 7'd0;
    cnt_0 = 7'd0;
    for (i=0;i<64;i=i+1) begin
        if (data_out_rr[i] == 1'b1) begin
            cnt_1 = cnt_1 + 1'b1;
        end
        else begin
            cnt_0 = cnt_0 + 1'b1;
        end
    end
end
  
always @(posedge clk or posedge rst) begin
    if (rst) begin
        dc_replace_en_r <= 1'b0;
    end
    else begin
        if (data_valid_r && ((data_r[7:0] != TS1) && (data_r[7:0] != TS2) && (data_r[7:0] != TSEQ))) begin
            dc_replace_en_r <= 1'b0;
        end
        else begin
            if (data_valid_r == 1'b1 && data_out_ready) begin
                if ((data_block_start_r == 1'b1) && (data_block_head_r == 4'b1100) && ((data_r[7:0] == TS1) || (data_r[7:0] == TS2) || (data_r[7:0] == TSEQ))) begin
                    dc_replace_en_r <= 1'b1;
                end
                else begin
                    dc_replace_en_r <= 1'b0;
                end
            end
        end
    end
end

always @(posedge clk or posedge rst) begin 
    if (rst) begin
        sds_detect_r <= 1'b1;
    end
    else begin
        if (data_valid_r == 1'b1 && data_out_ready) begin
            if ((data_block_start_r == 1'b1) && (data_block_head_r == 4'b1100)) begin
                if (data_r[7:0] == SDS) begin
                    sds_detect_r <= 1'b1;
                end
                else  begin
                    if (data_r[7:0] == 8'h00) begin
                        sds_detect_r <= 1'b0;
                    end
                end
            end
        end
    end
end

always @(*) begin
    if (dc_replace_en_r == 1'b1) begin
        if (dc_cnt > DC_CNT_1_31) begin
            dc_en_byte_7 = 8'h08; 
            dc_en_byte_6 = 8'h20; 
        end
        else begin
            if (dc_cnt > DC_CNT_1_15) begin
                dc_en_byte_7 = 8'h08; 
                dc_en_byte_6 = data_r[55:48];
            end
            else begin
                if (dc_cnt < DC_CNT_0_31) begin
                    dc_en_byte_7 = 8'hF7; 
                    dc_en_byte_6 = 8'hDF;
                end
                else begin
                    if (dc_cnt < DC_CNT_0_15) begin
                        dc_en_byte_7 = 8'hF7; 
                        dc_en_byte_6 = data_r[55:48];
                    end
                    else begin
                        dc_en_byte_7 = data_r[63:56];
                        dc_en_byte_6 = data_r[55:48];
                    end
                end
            end
        end
    end
    else begin
        dc_en_byte_7 = data_r[63:56];
        dc_en_byte_6 = data_r[55:48];
    end
end

endmodule


`ifdef MSIM
module pkt4p128b_v2
`else
module `getname( pkt4p128b_v2,`module_name)
`endif
(
	input	wire			TX_CLK, 
	input	wire			S_ARESETN,

	input	wire			S_VALID,
	output	wire			S_READY,
	input	wire	[63:0]	S_DATA,
	input	wire	[3:0]	S_SYNCHEAD,
	input	wire			S_STARTBLOCK,

	input	wire			TXREADY,
	output  reg				TXDATA_VALID,
	output	reg		[65:0]	TXDATA

);


assign S_READY = TXREADY;

reg [1:0] S_DATA_r;
always@(posedge TX_CLK) begin
	S_DATA_r <= S_DATA[1:0];
end

always@(posedge TX_CLK or negedge S_ARESETN) begin
	if(!S_ARESETN) begin
		TXDATA <= 66'b0;
		TXDATA_VALID <= 1'b0;
	end
	else begin
		if(TXREADY && S_VALID && S_STARTBLOCK) begin
			TXDATA_VALID <= 1'b1;
			TXDATA <= {S_SYNCHEAD, S_DATA[63:2]};
		end
		else if(TXREADY && S_VALID) begin
			TXDATA_VALID <= 1'b1;
			TXDATA <= {S_DATA_r[1:0],  S_DATA};
		end
		// else begin
		// 	TXDATA <= 66'b0;
		// 	TXDATA_VALID <= 1'b0;
		// end
	end
end
	
endmodule

`ifdef MSIM
module p132btxgears
`else
module `getname( p132btxgears,`module_name)
`endif
(
    input	wire	i_clk,
    input	wire	i_reset,
    
    output	wire		S_READY,
    input	wire		S_VALID,
    input	wire	[65:0]	S_DATA,
    
    input	wire		i_ready,
    output	wire	[63:0]	o_data
);

reg	[7:0]		r_count;
reg	[7:0]		r_count_r;
reg	[127:0]		gearbox;
reg	[128+64-1:0]	full_gears;
reg	[6:0]		shift;

always @(posedge i_clk)
if (i_reset)
begin
    r_count <= 1;	// = 64
    r_count_r <= 1;
    shift <= 0;
end else begin
    r_count_r <= r_count;
    if (r_count != 32 && i_ready && S_VALID && S_READY)
        r_count <= r_count + 1;
    else if (r_count == 32)
        r_count <= r_count - 31;

    if(S_VALID) begin
        shift <= shift + 2;
        if(shift == 64) begin
            shift <= 0;
        end
    end
end

assign	S_READY = ((r_count_r != 32) && i_ready && !i_reset);

always @(posedge i_clk)
begin
    if(i_reset) begin
        full_gears <= 0;
    end
    if(S_VALID && i_ready)begin
        if (r_count_r != 32)
            full_gears <= (full_gears | ({ 64'h0, S_DATA, 62'h0 } >> shift)) << 64;
        else
            full_gears <= full_gears << 64;
    end
end


assign	o_data = full_gears[191:128];

endmodule


`ifdef MSIM
module usb3_1_lfsr
`else
module `getname( usb3_1_lfsr,`module_name)
`endif
(
    input wire clk,
    input wire rst,
    input wire scram_rst,
    input wire 	[22:0] scram_init,
    input wire scram_en,
    input wire [63:0] data_in,
    output reg [63:0] data_out_c,
    output reg [63:0] data_out
);

reg [22:0] lfsr_q,lfsr_c;
reg [63:0] data_c;

always @(*) begin
    lfsr_c[0] = lfsr_q[0] ^ lfsr_q[3] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    lfsr_c[1] = lfsr_q[1] ^ lfsr_q[4] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    lfsr_c[2] = lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[10] ^ lfsr_q[17] ^ lfsr_q[21];
    lfsr_c[3] = lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[11] ^ lfsr_q[18] ^ lfsr_q[22];
    lfsr_c[4] = lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[12] ^ lfsr_q[19];
    lfsr_c[5] = lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[21] ^ lfsr_q[22];
    lfsr_c[6] = lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[22];
    lfsr_c[7] = lfsr_q[0] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[20];
    lfsr_c[8] = lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[13] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[22];
    lfsr_c[9] = lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[14] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21];
    lfsr_c[10] = lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[15] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    lfsr_c[11] = lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[16] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[22];
    lfsr_c[12] = lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[17] ^ lfsr_q[20] ^ lfsr_q[21];
    lfsr_c[13] = lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[18] ^ lfsr_q[21] ^ lfsr_q[22];
    lfsr_c[14] = lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[19] ^ lfsr_q[22];
    lfsr_c[15] = lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[20];
    lfsr_c[16] = lfsr_q[0] ^ lfsr_q[3] ^ lfsr_q[10] ^ lfsr_q[14] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[22];
    lfsr_c[17] = lfsr_q[1] ^ lfsr_q[4] ^ lfsr_q[11] ^ lfsr_q[15] ^ lfsr_q[19] ^ lfsr_q[21];
    lfsr_c[18] = lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[5] ^ lfsr_q[12] ^ lfsr_q[16] ^ lfsr_q[20] ^ lfsr_q[22];
    lfsr_c[19] = lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[6] ^ lfsr_q[13] ^ lfsr_q[17] ^ lfsr_q[21];
    lfsr_c[20] = lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[7] ^ lfsr_q[14] ^ lfsr_q[18] ^ lfsr_q[22];
    lfsr_c[21] = lfsr_q[1] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    lfsr_c[22] = lfsr_q[2] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];

    data_c[0]  = data_in[0]  ^ lfsr_q[22];
    data_c[1]  = data_in[1]  ^ lfsr_q[21];
    data_c[2]  = data_in[2]  ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[3]  = data_in[3]  ^ lfsr_q[19] ^ lfsr_q[21];
    data_c[4]  = data_in[4]  ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[5]  = data_in[5]  ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[21];
    data_c[6]  = data_in[6]  ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[7]  = data_in[7]  ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[8]  = data_in[8]  ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[9]  = data_in[9]  ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21];
    data_c[10] = data_in[10] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[11] = data_in[11] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[12] = data_in[12] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[13] = data_in[13] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21];
    data_c[14] = data_in[14] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20];
    data_c[15] = data_in[15] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19];
    data_c[16] = data_in[16] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18];
    data_c[17] = data_in[17] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17];
    data_c[18] = data_in[18] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16];
    data_c[19] = data_in[19] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15];
    data_c[20] = data_in[20] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[22];
    data_c[21] = data_in[21] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[21];
    data_c[22] = data_in[22] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[23] = data_in[23] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[24] = data_in[24] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21];
    data_c[25] = data_in[25] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[26] = data_in[26] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[21];
    data_c[27] = data_in[27] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[28] = data_in[28] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[21];
    data_c[29] = data_in[29] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[30] = data_in[30] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[31] = data_in[31] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[32] = data_in[32] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[33] = data_in[33] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[34] = data_in[34] ^ lfsr_q[0] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[35] = data_in[35] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[36] = data_in[36] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21];
    data_c[37] = data_in[37] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[38] = data_in[38] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[39] = data_in[39] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21];
    data_c[40] = data_in[40] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20];
    data_c[41] = data_in[41] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[22];
    data_c[42] = data_in[42] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[21];
    data_c[43] = data_in[43] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[20];
    data_c[44] = data_in[44] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[19] ^ lfsr_q[22];
    data_c[45] = data_in[45] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[18] ^ lfsr_q[21];
    data_c[46] = data_in[46] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[17] ^ lfsr_q[20];
    data_c[47] = data_in[47] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[16] ^ lfsr_q[19];
    data_c[48] = data_in[48] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[15] ^ lfsr_q[18] ^ lfsr_q[22];
    data_c[49] = data_in[49] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[14] ^ lfsr_q[17] ^ lfsr_q[21];
    data_c[50] = data_in[50] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[13] ^ lfsr_q[16] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[51] = data_in[51] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[8] ^ lfsr_q[9] ^ lfsr_q[12] ^ lfsr_q[15] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[52] = data_in[52] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[7] ^ lfsr_q[8] ^ lfsr_q[11] ^ lfsr_q[14] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[53] = data_in[53] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[6] ^ lfsr_q[7] ^ lfsr_q[10] ^ lfsr_q[13] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[54] = data_in[54] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[5] ^ lfsr_q[6] ^ lfsr_q[9] ^ lfsr_q[12] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[55] = data_in[55] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[4] ^ lfsr_q[5] ^ lfsr_q[8] ^ lfsr_q[11] ^ lfsr_q[15] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[56] = data_in[56] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[3] ^ lfsr_q[4] ^ lfsr_q[7] ^ lfsr_q[10] ^ lfsr_q[14] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[57] = data_in[57] ^ lfsr_q[0] ^ lfsr_q[2] ^ lfsr_q[3] ^ lfsr_q[6] ^ lfsr_q[9] ^ lfsr_q[13] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[58] = data_in[58] ^ lfsr_q[1] ^ lfsr_q[2] ^ lfsr_q[5] ^ lfsr_q[8] ^ lfsr_q[12] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[21];
    data_c[59] = data_in[59] ^ lfsr_q[0] ^ lfsr_q[1] ^ lfsr_q[4] ^ lfsr_q[7] ^ lfsr_q[11] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[60] = data_in[60] ^ lfsr_q[0] ^ lfsr_q[3] ^ lfsr_q[6] ^ lfsr_q[10] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[19] ^ lfsr_q[21];
    data_c[61] = data_in[61] ^ lfsr_q[2] ^ lfsr_q[5] ^ lfsr_q[9] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[22];
    data_c[62] = data_in[62] ^ lfsr_q[1] ^ lfsr_q[4] ^ lfsr_q[8] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[17] ^ lfsr_q[19] ^ lfsr_q[21] ^ lfsr_q[22];
    data_c[63] = data_in[63] ^ lfsr_q[0] ^ lfsr_q[3] ^ lfsr_q[7] ^ lfsr_q[9] ^ lfsr_q[10] ^ lfsr_q[11] ^ lfsr_q[12] ^ lfsr_q[13] ^ lfsr_q[14] ^ lfsr_q[15] ^ lfsr_q[16] ^ lfsr_q[18] ^ lfsr_q[20] ^ lfsr_q[21] ^ lfsr_q[22];

    data_out_c = data_c;
end // always

always @(posedge clk, posedge rst) begin
    if(rst) begin
        lfsr_q <= scram_init;
        data_out <= {64{1'b0}};
    end
    else begin
        lfsr_q <= scram_rst ? scram_init : scram_en ? lfsr_c : lfsr_q;
        data_out <= scram_en ? data_c : data_out;
    end
end // always
endmodule // scrambler


`ifdef MSIM
module upar_csr
`else
module `getname( upar_csr,`module_name)
`endif
(
    input clk_in,
    input rst_n,    
    output ahb_rstn_o,
    output test_dec_en_o,
    input rx_polarity,
    input c8b10b_en,
    input eidle_en,
    output reg eidle_en_ack,
    input tx_detect_rx_en,
    output reg tx_detect_rx_ack,
    output reg tx_detect_rx,
    input ffe_en,
    output reg ffe_en_ack,
    output reg upar_wren, // input  None
    output [23:0] upar_addr, // input [23:0] None
    output [31:0]upar_wrdata, // input [31:0] None
    output reg upar_rden, // input  None
    input [31:0]upar_rddata, // output [31:0] None
    input upar_rdvld, // output  None
    input upar_ready_i // output  None
);

reg eidle_en_d1;
reg eidle_en_d2;
reg tx_detect_rx_en_d1;
reg tx_detect_rx_en_d2;
reg rx_polarity_d1;
reg rx_polarity_d2;
reg c8b10b_en_d1;
reg c8b10b_en_d2;
reg ffe_en_d1;
reg ffe_en_d2;

localparam FSM_INIT  		        = 4'b0000;
localparam FSM_IDLE                 = 4'b0001;
localparam FSM_WRITE_EIDLE_1        = 4'b0010;
localparam FSM_WRITE_EIDLE_2        = 4'b0011;
localparam FSM_WRITE_PLUSE_1        = 4'b0100;
localparam FSM_WRITE_PLUSE_2        = 4'b0101;
localparam FSM_WRITE_RX_POLARITY    = 4'b0110;
localparam FSM_READ_RXDET           = 4'b0111;
localparam FSM_FFE_WRITE  		    = 4'b1000;


// localparam CSR_WRITE_CDR_0 = 24'h90057b;
// localparam CSR_WRITE_CDR_1 = 24'h900579;
// localparam CSR_WRITE_CDR_2 = 24'h900585;
// localparam CSR_WRITE_CDR_3 = 24'h900586;
// localparam CSR_WRITE_CDR_4 = 24'h900432;
// localparam CSR_WRITE_CDR_5 = 24'h900433;
// localparam CSR_WRITE_CDR_6 = 24'h9003b8;
// localparam CSR_WRITE_CDR_7 = 24'h90045b;
// localparam CSR_WRITE_CDR_8 = 24'h90045c;

localparam CSR_WRITE_CDR_CFG = 24'h9083f8;
localparam CSR_WRITE_LN_CTRL = 24'h908830;
// localparam CSR_WRITE_CDR_CFG_0 = 24'h900453;
// localparam CSR_WRITE_CDR_CFG_1 = 24'h90045e;
// localparam CSR_WRITE_CDR_CFG_2 = 24'h90045f;
// localparam CSR_WRITE_CDR_CFG_3 = 24'h900454;
// localparam CSR_WRITE_CDR_CFG_4 = 24'h900460;
// localparam CSR_WRITE_CDR_CFG_5 = 24'h900461;

`ifdef Q0_LN0 
localparam CSR_WRITE_EIDLE = 24'h8003a4;
localparam CSR_WRITE_PLUSE = 24'h80033f;
localparam CSR_WRITE_8B10B = 24'h809068;
localparam CSR_WRITE_RX_POLARITY = 24'h809008;
localparam CSR_READ_RXDET  = 24'h808b34;
localparam CSR_TX_FFE_0 = 24'h808234;
localparam CSR_TX_FFE_1 = 24'h808238;
localparam CSR_TX_FFE_2 = 24'h8082d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h800253;
localparam CSR_WRITE_CDR_CFG_1 = 24'h80025e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h80025f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h800254;
localparam CSR_WRITE_CDR_CFG_4 = 24'h800260;
localparam CSR_WRITE_CDR_CFG_5 = 24'h800261;
`elsif Q0_LN1
localparam CSR_WRITE_EIDLE = 24'h8005a4;
localparam CSR_WRITE_PLUSE = 24'h80053f;
localparam CSR_WRITE_8B10B = 24'h809268;
localparam CSR_WRITE_RX_POLARITY = 24'h809208;
localparam CSR_READ_RXDET  = 24'h808c34;
localparam CSR_TX_FFE_0 = 24'h808334;
localparam CSR_TX_FFE_1 = 24'h808338;
localparam CSR_TX_FFE_2 = 24'h8083d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h800453;
localparam CSR_WRITE_CDR_CFG_1 = 24'h80045e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h80045f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h800454;
localparam CSR_WRITE_CDR_CFG_4 = 24'h800460;
localparam CSR_WRITE_CDR_CFG_5 = 24'h800461;
`elsif Q0_LN2
localparam CSR_WRITE_EIDLE = 24'h8007a4;
localparam CSR_WRITE_PLUSE = 24'h80073f;
localparam CSR_WRITE_8B10B = 24'h809468;
localparam CSR_WRITE_RX_POLARITY = 24'h809408;
localparam CSR_READ_RXDET  = 24'h808d34;
localparam CSR_TX_FFE_0 = 24'h808434;
localparam CSR_TX_FFE_1 = 24'h808438;
localparam CSR_TX_FFE_2 = 24'h8084d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h800653;
localparam CSR_WRITE_CDR_CFG_1 = 24'h80065e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h80065f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h800654;
localparam CSR_WRITE_CDR_CFG_4 = 24'h800660;
localparam CSR_WRITE_CDR_CFG_5 = 24'h800661;
`elsif Q0_LN3
localparam CSR_WRITE_EIDLE = 24'h8009a4;
localparam CSR_WRITE_PLUSE = 24'h80093f;
localparam CSR_WRITE_8B10B = 24'h809668;
localparam CSR_WRITE_RX_POLARITY = 24'h809608;
localparam CSR_READ_RXDET  = 24'h808e34;
localparam CSR_TX_FFE_0 = 24'h808534;
localparam CSR_TX_FFE_1 = 24'h808538;
localparam CSR_TX_FFE_2 = 24'h8085d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h800853;
localparam CSR_WRITE_CDR_CFG_1 = 24'h80085e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h80085f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h800854;
localparam CSR_WRITE_CDR_CFG_4 = 24'h800860;
localparam CSR_WRITE_CDR_CFG_5 = 24'h800861;
`elsif Q1_LN0
localparam CSR_WRITE_EIDLE = 24'h9003a4;
localparam CSR_WRITE_PLUSE = 24'h90033f;
localparam CSR_WRITE_8B10B = 24'h909068;
localparam CSR_WRITE_RX_POLARITY = 24'h909008;
localparam CSR_READ_RXDET  = 24'h908b34;
localparam CSR_TX_FFE_0 = 24'h908234;
localparam CSR_TX_FFE_1 = 24'h908238;
localparam CSR_TX_FFE_2 = 24'h9082d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h900253;
localparam CSR_WRITE_CDR_CFG_1 = 24'h90025e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h90025f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h900254;
localparam CSR_WRITE_CDR_CFG_4 = 24'h900260;
localparam CSR_WRITE_CDR_CFG_5 = 24'h900261;
`elsif Q1_LN1
localparam CSR_WRITE_EIDLE = 24'h9005a4;
localparam CSR_WRITE_PLUSE = 24'h90053f;
localparam CSR_WRITE_8B10B = 24'h909268;
localparam CSR_WRITE_RX_POLARITY = 24'h909208;
localparam CSR_READ_RXDET  = 24'h908c34;
localparam CSR_TX_FFE_0 = 24'h908334;
localparam CSR_TX_FFE_1 = 24'h908338;
localparam CSR_TX_FFE_2 = 24'h9083d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h900453;
localparam CSR_WRITE_CDR_CFG_1 = 24'h90045e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h90045f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h900454;
localparam CSR_WRITE_CDR_CFG_4 = 24'h900460;
localparam CSR_WRITE_CDR_CFG_5 = 24'h900461;
`elsif Q1_LN2
localparam CSR_WRITE_EIDLE = 24'h9007a4;
localparam CSR_WRITE_PLUSE = 24'h90073f;
localparam CSR_WRITE_8B10B = 24'h909468;
localparam CSR_WRITE_RX_POLARITY = 24'h909408;
localparam CSR_READ_RXDET  = 24'h908d34;
localparam CSR_TX_FFE_0 = 24'h908434;
localparam CSR_TX_FFE_1 = 24'h908438;
localparam CSR_TX_FFE_2 = 24'h9084d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h900653;
localparam CSR_WRITE_CDR_CFG_1 = 24'h90065e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h90065f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h900654;
localparam CSR_WRITE_CDR_CFG_4 = 24'h900660;
localparam CSR_WRITE_CDR_CFG_5 = 24'h900661;
`elsif Q1_LN3
localparam CSR_WRITE_EIDLE = 24'h9009a4;
localparam CSR_WRITE_PLUSE = 24'h90093f;
localparam CSR_WRITE_8B10B = 24'h909668;
localparam CSR_WRITE_RX_POLARITY = 24'h909608;
localparam CSR_READ_RXDET  = 24'h908e34;
localparam CSR_TX_FFE_0 = 24'h908534;
localparam CSR_TX_FFE_1 = 24'h908538;
localparam CSR_TX_FFE_2 = 24'h9085d8;
localparam CSR_WRITE_CDR_CFG_0 = 24'h900853;
localparam CSR_WRITE_CDR_CFG_1 = 24'h90085e;
localparam CSR_WRITE_CDR_CFG_2 = 24'h90085f;
localparam CSR_WRITE_CDR_CFG_3 = 24'h900854;
localparam CSR_WRITE_CDR_CFG_4 = 24'h900860;
localparam CSR_WRITE_CDR_CFG_5 = 24'h900861;
`endif


reg [3:0] state;
reg [2:0] next_state;
reg [31:0] csr_value;
reg [23:0] csr_addr;
reg	[11:0] cnt0;

assign upar_addr = csr_addr;
assign upar_wrdata = csr_value;

always @(posedge clk_in or negedge rst_n) begin
    if(~rst_n) 
	begin
        eidle_en_d1 <= 1;
        eidle_en_d2 <= 1;
		tx_detect_rx_en_d1 <= 0;
		tx_detect_rx_en_d2 <= 0;
        rx_polarity_d1 <= 0;
        rx_polarity_d2 <= 0;
        c8b10b_en_d1 <= 1;
        c8b10b_en_d2 <= 1;
        ffe_en_d1 <= 1;
        ffe_en_d2 <= 1;
	end
    else
	begin
        eidle_en_d1 <= eidle_en;
        eidle_en_d2 <= eidle_en_d1;
		tx_detect_rx_en_d1 <= tx_detect_rx_en;
		tx_detect_rx_en_d2 <= tx_detect_rx_en_d1;
        rx_polarity_d1 <= rx_polarity;
        rx_polarity_d2 <= rx_polarity_d1;
        c8b10b_en_d1 <= c8b10b_en;
        c8b10b_en_d2 <= c8b10b_en_d1;
        ffe_en_d1 <= ffe_en;
        ffe_en_d2 <= ffe_en_d1;
	end
end


reg eidle_req,eidle_req_done,eidle_enable_req,eidle_disable_req;
reg tx_detect_rx_en_req,tx_detect_rx_en_req_done,tx_detect_rx_en_enable_req,tx_detect_rx_en_disable_req;
reg rx_polarity_req,rx_polarity_req_done,rx_polarity_enable_req,rx_polarity_disable_req;
reg c8b10b_en_req,c8b10b_en_req_done,c8b10b_en_enable_req,c8b10b_en_disable_req;
reg ffe_req,ffe_req_done,ffe_enable_req,ffe_disable_req;
reg pluse_done;
reg reset_done;

always @ (posedge clk_in)
begin
    eidle_req <= (eidle_en_d1 ^ eidle_en_d2 ==1'b1)? 1'b1 : eidle_req_done? 1'b0 : eidle_req;
    tx_detect_rx_en_enable_req <= ({tx_detect_rx_en_d2,tx_detect_rx_en_d1}==2'b01)? 1'b1 : pluse_done? 1'b0 : tx_detect_rx_en_enable_req;
    tx_detect_rx_en_disable_req <= {tx_detect_rx_en_d2,tx_detect_rx_en_d1}==2'b10;
    rx_polarity_req <= (rx_polarity_d1 ^ rx_polarity_d2 ==1'b1)? 1'b1 : rx_polarity_req_done? 1'b0 : rx_polarity_req;
    c8b10b_en_req <= (c8b10b_en_d1 ^ c8b10b_en_d2 ==1'b1)? 1'b1 : c8b10b_en_req_done? 1'b0 : c8b10b_en_req;
    ffe_req <= (ffe_en_d1 ^ ffe_en_d2 ==1'b1)? 1'b1 : ffe_req_done? 1'b0 : ffe_req;
end

reg test_eleidle = 0;
always @(posedge clk_in or negedge rst_n) begin
    if(~rst_n) begin
        csr_value <= 32'h01;
        csr_addr <= 24'h0;
		cnt0 <= 0;
        tx_detect_rx_ack <= 0;
        tx_detect_rx <= 0;
        upar_wren <= 1'b0;
        pluse_done <= 1'b0;
        reset_done <= 1'b0;
        state <= FSM_INIT;
    end
    else begin
		eidle_req_done <= 1'b0;
		ffe_req_done <= 1'b0;
        case(state) 
            FSM_INIT : begin
                upar_rden <= 1'b0;
                upar_wren <= 1'b1;
                if(cnt0 == 0) begin
                    csr_addr <= CSR_TX_FFE_0;
                    csr_value <= 32'h0000F000;
                end
                else if(cnt0 == 1) begin
                    csr_addr <= CSR_TX_FFE_1;
                    csr_value <= 32'h0;
                end
                else if(cnt0 == 2) begin
                    csr_addr <= CSR_TX_FFE_2;
                    csr_value <= 32'h00000110;
                end
                else if(cnt0 == 3) begin
                    csr_addr <= CSR_WRITE_CDR_CFG;
                    csr_value <= 32'h00038002;
                end
                else if(cnt0 == 4) begin
                    csr_addr <= CSR_WRITE_LN_CTRL;
                    csr_value <= 32'hFFFFF9FF;
                end
                else if(cnt0 == 5) begin
                    csr_addr <= CSR_WRITE_CDR_CFG_0;
                    csr_value <= 32'h7F000000;
                end
                else if(cnt0 == 6) begin
                    csr_addr <= CSR_WRITE_CDR_CFG_1;
                    csr_value <= 32'h007F0000;
                end
                else if(cnt0 == 7) begin
                    csr_addr <= CSR_WRITE_CDR_CFG_2;
                    csr_value <= 32'h7F000000;
                end
                else if(cnt0 == 8) begin
                    csr_addr <= CSR_WRITE_CDR_CFG_3;
                    csr_value <= 32'h0000004F;
                end
                else if(cnt0 == 9) begin
                    csr_addr <= CSR_WRITE_CDR_CFG_4;
                    csr_value <= 32'h0000004F;
                end
                else if(cnt0 == 10) begin
                    csr_addr <= CSR_WRITE_CDR_CFG_5;
                    csr_value <= 32'h00004F00;
                end
                // else if(cnt0 == 3) begin
                    // csr_addr <= CSR_WRITE_CDR_0;
                    // csr_value <= 32'hD2000000;
                // end
                // else if(cnt0 == 4) begin
                    // csr_addr <= CSR_WRITE_CDR_1;
                    // csr_value <= 32'h0000D200;
                // end
                // else if(cnt0 == 5) begin
                    // csr_addr <= CSR_WRITE_CDR_2;
                    // csr_value <= 32'h0000D200;
                // end
                // else if(cnt0 == 6) begin
                    // csr_addr <= CSR_WRITE_CDR_3;
                    // csr_value <= 32'h00D20000;
                // end
                // else if(cnt0 == 7) begin
                    // csr_addr <= CSR_WRITE_CDR_4;
                    // csr_value <= 32'h00D20000;
                // end
                // else if(cnt0 == 8) begin
                    // csr_addr <= CSR_WRITE_CDR_5;
                    // csr_value <= 32'hD2000000;
                // end
                // else if(cnt0 == 9) begin
                    // csr_addr <= CSR_WRITE_CDR_6;
                    // csr_value <= 32'hA0000030;
                // end
                // else if(cnt0 == 10) begin
                    // csr_addr <= CSR_WRITE_CDR_7;
                    // csr_value <= 32'h70000000;
                // end
                // else if(cnt0 == 11) begin
                    // csr_addr <= CSR_WRITE_CDR_8;
                    // csr_value <= 32'h0000007D;
                // end

                // if(upar_ready_i)
                // begin
                    // upar_wren <= 1'b0;
                    // if(cnt0 == 10)
                        state <=FSM_IDLE;
                    // else
                        // cnt0 <= cnt0 + 1'b1;
                // end
            end

            FSM_IDLE: begin
                reset_done <= 1'b0;
                tx_detect_rx <= 1'b0;
                tx_detect_rx_ack <= 1'b0;
                upar_wren <= 1'b0;
                upar_rden <= 1'b0;
				cnt0 <= 0;
                pluse_done <= 1'b0;
                // eidle_req_done <= 1'b0;
				eidle_en_ack <= 1'b0;
				ffe_en_ack <= 1'b0;
                c8b10b_en_req_done <= 1'b0;
                rx_polarity_req_done <= 1'b0;
                if(eidle_req)
				begin
					state <= FSM_WRITE_EIDLE_1;
					eidle_req_done <= 1'b1;
				end
                else if(ffe_req)
				begin
					state <= FSM_FFE_WRITE;
					ffe_req_done <= 1'b1;
				end
				else if(tx_detect_rx_en_enable_req)
				begin
					state <= FSM_WRITE_PLUSE_1;
				end
                // else if(c8b10b_en_req)
                // begin
                //     state <= FSM_WRITE_8B10B;
                // end
                else if(rx_polarity_req)
                begin
                    state <= FSM_WRITE_RX_POLARITY;
                end
				else
				begin
					state <= FSM_IDLE;
				end
            end
            FSM_WRITE_EIDLE_1: begin
				test_eleidle <= 1'b1;
                upar_rden <= 1'b0;
                upar_wren <= 1'b1;
                csr_addr <= CSR_WRITE_EIDLE;
                if(eidle_en_d1)
                    csr_value <= 32'h1;
                else
                    csr_value <= 32'h7;
                
                if(upar_ready_i)
                begin
                    state <=FSM_IDLE;
					eidle_en_ack <= 1'b1;
                end
            end
            FSM_WRITE_EIDLE_2: begin
                upar_rden <= 1'b1;
                upar_wren <= 1'b0;
                csr_addr <= CSR_WRITE_EIDLE;
                
                if(upar_rdvld)
                begin
					if(upar_rddata == 1 && eidle_en_d1)
					begin
						state <=FSM_IDLE;
						eidle_en_ack <= 1'b1;
					end
					else if(upar_rddata == 7 && !eidle_en_d1)
					begin
						state <=FSM_IDLE;
						eidle_en_ack <= 1'b1;
					end
					else
					begin
						state <=FSM_WRITE_EIDLE_1;
						eidle_en_ack <= 1'b0;
					end
                end
            end
            FSM_WRITE_PLUSE_1: begin
                upar_rden <= 1'b0;
				cnt0 <= 0;
                csr_addr <= CSR_WRITE_PLUSE;
                upar_wren <= 1'b1;
                csr_value <= 32'h03000000;
                if(upar_ready_i)
                    state <=FSM_WRITE_PLUSE_2;
            end
            FSM_WRITE_PLUSE_2: begin
                upar_rden <= 1'b0;
                csr_addr <= CSR_WRITE_PLUSE;
				if(cnt0 >= 250)
				begin
					upar_wren <= 1'b1;
					csr_value <= 32'h00000000;
                    pluse_done <= 1'b1;
				end
				else 
				begin
					upar_wren <= 1'b0;
					csr_value <= 32'h00000000;
				end

                if(upar_ready_i)
                begin
                    state <=FSM_READ_RXDET;
                    cnt0 <= 0;
                end
                else
                begin
				    cnt0 <= cnt0 + 1'b1;
                end
            end
            // FSM_WRITE_8B10B: begin
            //     upar_wren <= 1'b1;
            //     csr_addr <= CSR_WRITE_8B10B;
            //     c8b10b_en_req_done <= 1'b1;
            //     if(c8b10b_en_d1)
            //         csr_value <= 32'h172;
            //     else
            //         csr_value <= 32'h1ff;
                
            //     if(upar_ready_i)
            //     begin
            //         state <=FSM_IDLE;
            //     end
            // end
            FSM_WRITE_RX_POLARITY: begin
                upar_wren <= 1'b1;
                csr_addr <= CSR_WRITE_RX_POLARITY;
                rx_polarity_req_done <= 1'b1;
                if(rx_polarity_d1)
                    csr_value <= 32'h80;
                else
                    csr_value <= 32'h0;
                
                if(upar_ready_i)
                begin
                    state <=FSM_IDLE;
                end
            end
			FSM_READ_RXDET: begin
                cnt0 <= cnt0 + 1'b1;
                upar_wren <= 1'b0;
                csr_addr <= CSR_READ_RXDET;
                upar_rden <= 1'b1;
                if(upar_rddata[0] && upar_rdvld)
                begin
                    tx_detect_rx <= 1'b1;
                    tx_detect_rx_ack <= 1'b1;
                    state <=FSM_IDLE;
                end
                else if(cnt0[8])
                begin
					//----------------
                    state <=FSM_WRITE_PLUSE_1;
                    //// tx_detect_rx_ack <= 1'b1;
					//----------------
					// tx_detect_rx <= 1'b1;
                    // tx_detect_rx_ack <= 1'b1;
                    // state <=FSM_IDLE;
                end
                else if(tx_detect_rx_en_disable_req)
                begin
                    state <=FSM_IDLE;
                    tx_detect_rx_ack <= 1'b1;
                end
			end
            FSM_FFE_WRITE : begin
                upar_rden <= 1'b0;
                upar_wren <= 1'b1;
                if(cnt0 == 0) begin
                    csr_addr <= CSR_TX_FFE_1;
                    if(ffe_en_d1) csr_value <= 32'h0;
                    else csr_value <= 32'h00000805;
                end
                else if(cnt0 == 1) begin
                    csr_addr <= CSR_TX_FFE_2;
                    csr_value <= 32'h00000000;
                end
                else if(cnt0 == 2) begin
                    csr_addr <= CSR_TX_FFE_2;
                    csr_value <= 32'h00000110;
                end

                
                if(upar_ready_i)
                begin
                    upar_wren <= 1'b0;
                    if(cnt0 == 2)
                        state <=FSM_IDLE;
                    else begin
                        cnt0 <= cnt0 + 1'b1;
                        ffe_en_ack <= 1'b1;
                    end
                end
            end
        endcase
    end
end

endmodule



`ifdef MSIM
module usb3_lfps_detector
`else
module `getname(usb3_lfps_detector,`module_name) 
`endif
(
    input           clk, //156.25MHz
    input           rstn,

    input   [63:0]  rx_data,

    output          lfps_detect
);



parameter CNT_PERIOD_MIN        = 32'd2;
parameter CNT_PERIOD_MAX        = 32'd16;


// reg     [31:0]      cnt0;
// reg     [31:0]      cnt1;
reg     [4:0]       cnt2;
reg     [6:0]       cnt3;
reg     [5:0]       cnt4;

reg     [63:0]      rx_data_r [4:0];
reg                 rx_data_r1;
reg                 rx_data_r2;
reg     [3:0]       state;

reg                 lfps_detect_r;
reg     [7:0]       lfps_detect_r2;
reg                 lfps_detect_r3;
reg                 lfps_detect1;
reg                 lfps_detect2;


integer i;


assign lfps_detect      = lfps_detect_r3;

always@(posedge clk or negedge rstn)
begin
    if(!rstn)
    begin
        rx_data_r1      <= 40'h0;
        rx_data_r2      <= 40'h0;
        cnt3            <= 6'd0;
        cnt4            <= 6'd0;
        lfps_detect1    <= 1'b0;
        lfps_detect2    <= 1'b0;
    end
    else
    begin
        lfps_detect1    <= 1'b0;
        rx_data_r2      <= rx_data_r1;
             if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFFF && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd0; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFFE && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd1; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFFC && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd2; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFF8 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd3; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFF0 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd4; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFE0 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd5; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFFC0 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd6; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFF80 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd7; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFF00 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd8; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFE00 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd9; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFFC00 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd10; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFF800 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd11; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFF000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd12; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFE000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd13; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFFC000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd14; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFF8000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd15; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFF0000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd16; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFE0000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd17; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFFC0000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd18; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFF80000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd19; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFF00000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd20; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFE00000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd21; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFFC00000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd22; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFF800000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd23; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFF000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd24; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFE000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd25; end
        else if(rx_data_r[0] == 64'hFFFFFFFFFC000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd26; end
        else if(rx_data_r[0] == 64'hFFFFFFFFF8000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd27; end
        else if(rx_data_r[0] == 64'hFFFFFFFFF0000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd28; end
        else if(rx_data_r[0] == 64'hFFFFFFFFE0000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd29; end
        else if(rx_data_r[0] == 64'hFFFFFFFFC0000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd30; end
        else if(rx_data_r[0] == 64'hFFFFFFFF80000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd31; end
        else if(rx_data_r[0] == 64'hFFFFFFFF00000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd32; end
        else if(rx_data_r[0] == 64'hFFFFFFFE00000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd33; end
        else if(rx_data_r[0] == 64'hFFFFFFFC00000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd34; end
        else if(rx_data_r[0] == 64'hFFFFFFF800000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd35; end
        else if(rx_data_r[0] == 64'hFFFFFFF000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd36; end
        else if(rx_data_r[0] == 64'hFFFFFFE000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd37; end
        else if(rx_data_r[0] == 64'hFFFFFFC000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd38; end
        else if(rx_data_r[0] == 64'hFFFFFF8000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd39; end
        else if(rx_data_r[0] == 64'hFFFFFF0000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd40; end
        else if(rx_data_r[0] == 64'hFFFFFE0000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd41; end
        else if(rx_data_r[0] == 64'hFFFFFC0000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd42; end
        else if(rx_data_r[0] == 64'hFFFFF80000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd43; end
        else if(rx_data_r[0] == 64'hFFFFF00000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd44; end
        else if(rx_data_r[0] == 64'hFFFFE00000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd45; end
        else if(rx_data_r[0] == 64'hFFFFC00000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd46; end
        else if(rx_data_r[0] == 64'hFFFF800000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd47; end
        else if(rx_data_r[0] == 64'hFFFF000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd48; end
        else if(rx_data_r[0] == 64'hFFFE000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd49; end
        else if(rx_data_r[0] == 64'hFFFC000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd50; end
        else if(rx_data_r[0] == 64'hFFF8000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd51; end
        else if(rx_data_r[0] == 64'hFFF0000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd52; end
        else if(rx_data_r[0] == 64'hFFE0000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd53; end
        else if(rx_data_r[0] == 64'hFFC0000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd54; end
        else if(rx_data_r[0] == 64'hFF80000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd55; end
        else if(rx_data_r[0] == 64'hFF00000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd56; end
        else if(rx_data_r[0] == 64'hFE00000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd57; end
        else if(rx_data_r[0] == 64'hFC00000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd58; end
        else if(rx_data_r[0] == 64'hF800000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd59; end
        else if(rx_data_r[0] == 64'hF000000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd60; end
        else if(rx_data_r[0] == 64'hE000000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd61; end
        else if(rx_data_r[0] == 64'hC000000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd62; end
        else if(rx_data_r[0] == 64'h8000000000000000 && rx_data_r[1][39:0] == 40'h0000000000) begin lfps_detect1 <= 1'b1; cnt3 <= 6'd63; end
        
 
        if(lfps_detect1)
        begin
            cnt4            <= 6'd0;
        end
        else if(lfps_detect2)
        begin
            cnt4            <= cnt4 + 1'b1;
        end
        else
        begin
            cnt4            <= 6'd0;
        end

        if(lfps_detect1)
        begin
            lfps_detect2    <= 1'b1;
        end
        else if(cnt4 > 32)
        begin
            lfps_detect2    <= 1'b0;
        end

        case(cnt3)
            6'd0   : rx_data_r1      <= rx_data_r[1][31];
            6'd1   : rx_data_r1      <= rx_data_r[1][30];
            6'd2   : rx_data_r1      <= rx_data_r[1][29];
            6'd3   : rx_data_r1      <= rx_data_r[1][28];
            6'd4   : rx_data_r1      <= rx_data_r[1][27];
            6'd5   : rx_data_r1      <= rx_data_r[1][26];
            6'd6   : rx_data_r1      <= rx_data_r[1][25];
            6'd7   : rx_data_r1      <= rx_data_r[1][24];
            6'd8   : rx_data_r1      <= rx_data_r[1][23];
            6'd9   : rx_data_r1      <= rx_data_r[1][22];
            6'd10  : rx_data_r1      <= rx_data_r[1][21];
            6'd11  : rx_data_r1      <= rx_data_r[1][20];
            6'd12  : rx_data_r1      <= rx_data_r[1][19];
            6'd13  : rx_data_r1      <= rx_data_r[1][18];
            6'd14  : rx_data_r1      <= rx_data_r[1][17];
            6'd15  : rx_data_r1      <= rx_data_r[1][16];
            6'd16  : rx_data_r1      <= rx_data_r[1][15];
            6'd17  : rx_data_r1      <= rx_data_r[1][14];
            6'd18  : rx_data_r1      <= rx_data_r[1][13];
            6'd19  : rx_data_r1      <= rx_data_r[1][12];
            6'd20  : rx_data_r1      <= rx_data_r[1][11];
            6'd21  : rx_data_r1      <= rx_data_r[1][10];
            6'd22  : rx_data_r1      <= rx_data_r[1][9];
            6'd23  : rx_data_r1      <= rx_data_r[1][8];
            6'd24  : rx_data_r1      <= rx_data_r[1][7];
            6'd25  : rx_data_r1      <= rx_data_r[1][6];
            6'd26  : rx_data_r1      <= rx_data_r[1][5];
            6'd27  : rx_data_r1      <= rx_data_r[1][4];
            6'd28  : rx_data_r1      <= rx_data_r[1][3];
            6'd29  : rx_data_r1      <= rx_data_r[1][2];
            6'd30  : rx_data_r1      <= rx_data_r[1][1];
            6'd31  : rx_data_r1      <= rx_data_r[0][0];
            6'd32  : rx_data_r1      <= rx_data_r[0][1];
            6'd33  : rx_data_r1      <= rx_data_r[0][2];
            6'd34  : rx_data_r1      <= rx_data_r[0][3];
            6'd35  : rx_data_r1      <= rx_data_r[0][4];
            6'd36  : rx_data_r1      <= rx_data_r[0][5];
            6'd37  : rx_data_r1      <= rx_data_r[0][6];
            6'd38  : rx_data_r1      <= rx_data_r[0][7];
            6'd39  : rx_data_r1      <= rx_data_r[0][8];
            6'd40  : rx_data_r1      <= rx_data_r[0][9];
            6'd41  : rx_data_r1      <= rx_data_r[0][10];
            6'd42  : rx_data_r1      <= rx_data_r[0][11];
            6'd43  : rx_data_r1      <= rx_data_r[0][12];
            6'd44  : rx_data_r1      <= rx_data_r[0][13];
            6'd45  : rx_data_r1      <= rx_data_r[0][14];
            6'd46  : rx_data_r1      <= rx_data_r[0][15];
            6'd47  : rx_data_r1      <= rx_data_r[0][16];
            6'd48  : rx_data_r1      <= rx_data_r[0][17];
            6'd49  : rx_data_r1      <= rx_data_r[0][18];
            6'd50  : rx_data_r1      <= rx_data_r[0][19];
            6'd51  : rx_data_r1      <= rx_data_r[0][20];
            6'd52  : rx_data_r1      <= rx_data_r[0][21];
            6'd53  : rx_data_r1      <= rx_data_r[0][22];
            6'd54  : rx_data_r1      <= rx_data_r[0][23];
            6'd55  : rx_data_r1      <= rx_data_r[0][24];
            6'd56  : rx_data_r1      <= rx_data_r[0][25];
            6'd57  : rx_data_r1      <= rx_data_r[0][26];
            6'd58  : rx_data_r1      <= rx_data_r[0][27];
            6'd59  : rx_data_r1      <= rx_data_r[0][28];
            6'd60  : rx_data_r1      <= rx_data_r[0][29];
            6'd61  : rx_data_r1      <= rx_data_r[0][30];
            6'd62  : rx_data_r1      <= rx_data_r[0][31];
            6'd63  : rx_data_r1      <= rx_data_r[0][32];
            default   : 
                rx_data_r1      <= rx_data_r[0][0];
        endcase

    end
end

always@(posedge clk or negedge rstn)
begin
    if(!rstn)
    begin
        lfps_detect_r    <= 1'b0;
        cnt2            <= 4'd0;
    end
    else
    begin
        if(lfps_detect2)
        begin
            if(rx_data_r2 && !rx_data_r1)
            begin
                cnt2            <= 4'd0;
                if(cnt2 >= CNT_PERIOD_MIN && cnt2 <= CNT_PERIOD_MAX)
                begin
                    lfps_detect_r    <= 1'b1;
                end
                else
                begin
                    lfps_detect_r    <= 1'b0;
                end
            end
            else
            begin
                cnt2            <= cnt2 + 1'b1;
            end
        end
        else
        begin
            lfps_detect_r    <= 1'b0;
            cnt2            <= 4'd0;
        end
    end
end

always@(posedge clk or negedge rstn)
begin
    if(!rstn)
    begin
        lfps_detect_r2  <= 8'b0;
    end
    else
    begin
        lfps_detect_r2  <= {lfps_detect_r2[6:0], lfps_detect_r};
    end
end

always@(posedge clk or negedge rstn)
begin
    if(!rstn)
    begin
        lfps_detect_r3  <= 1'b0;
    end
    else
    begin
        if(lfps_detect_r2 == 8'hff)
        begin
            lfps_detect_r3  <= 1'b1;
        end
        else if(lfps_detect_r2 == 8'h00)
        begin
            lfps_detect_r3  <= 1'b0;
        end
    end
end

always@(posedge clk or negedge rstn)
begin
    if(!rstn)
    begin
        for(i = 0; i < 5; i = i + 1) begin
            rx_data_r[i]    <= 40'b0;
        end
    end
    else
    begin
        rx_data_r[0]  <= rx_data;
        for(i = 0; i < 4; i = i + 1) begin
            rx_data_r[i+1]  <= rx_data_r[i];
        end
    end
end

endmodule




// module pulse_detect(
`ifdef MSIM
module pulse_detect
`else
module `getname(pulse_detect,`module_name) 
`endif
(
    input              clk_fast    , 
    input              clk_slow    ,   
    input              rst_n       ,
    input               data_in     ,
    output           dataout
);
  reg data_in_fast;
  reg [2:0] data_slow;
  always@(posedge clk_fast or negedge rst_n)begin
      if(!rst_n)
          data_in_fast<= 0;
      else
          data_in_fast<= data_in ? (~data_in_fast) : data_in_fast;
  end
  always@(posedge clk_slow or negedge rst_n)begin
      if(!rst_n)
          data_slow <= 3'b0;
      else
          data_slow <= {data_slow[1:0],data_in_fast};
  end   
  
  assign dataout = data_slow[2] ^ data_slow[1]; 
endmodule

//
// File name          :async_fifo.v
// Module name        :async_fifo.v
// Created by         :GoWin Semi
// Author             :(Winson)
// Created On         :2020-09-07 09:25 GuangZhou
// Last Modified      :
// Update Count       :2020-09-07 09:25
// Description        :
//                     
//                     
//----------------------------------------------------------------------
`ifdef MSIM
module async_fifo
`else
module `getname(async_fifo,`module_name) 
`endif
#(
      parameter             DSIZE = 40,
      parameter             ASIZE = 10,
      parameter             AEMPT = 1,
      parameter             AFULL = 32
)(
      output reg [DSIZE-1:0]   Q,
      output reg               Full,
      output reg               Empty,
      output reg               AlmostEmpty,
      output reg               AlmostFull,
      output reg [ASIZE:0]   RdDataNum,
      output reg [ASIZE:0]   WrDataNum,
      input   [DSIZE-1:0]   Data,
      input                 WrEn,
      input                 WrClock,
      input                 WPReset,
      input                 RdEn,
      input                 RdClock,
      input                 RPReset
);

      reg       [ASIZE:0]   wptr;
      reg       [ASIZE:0]   rptr; 
      reg       [ASIZE:0]   wq2_rptr;
      reg       [ASIZE:0]   rq2_wptr; 
      reg       [ASIZE:0]   wq1_rptr;
      reg       [ASIZE:0]   rq1_wptr;
      reg       [ASIZE:0]   rbin;
      reg       [ASIZE:0]   wbin;

      reg       [DSIZE-1:0] mem[0:(1<<ASIZE)-1];

      wire      [ASIZE-1:0] waddr;
      wire      [ASIZE-1:0] raddr;
      wire      [ASIZE:0]   rgraynext;
      wire      [ASIZE:0]   rbinnext;
      wire      [ASIZE:0]   wgraynext;
      wire      [ASIZE:0]   wbinnext;
      wire                  rempty_val;
      wire                  wfull_val;
      wire      [ASIZE:0]   wcount_r;
      wire      [ASIZE:0]   rcnt_sub;
      wire      [ASIZE:0]   rcount_w;
      wire      [ASIZE:0]   wcnt_sub;    

      always@(posedge RdClock, posedge RPReset)
      begin
          //if (RPReset) begin
          //    Q <= 0;
          //end
          //else if (RdEn) begin
          //    Q <= mem[raddr];
          //end
          if (RPReset) begin
              Q <= 0;
          end
          else begin
              Q <= mem[raddr];
          end    
      end

      always@(posedge WrClock)
      begin
        if(WrEn && !Full)
          mem[waddr] <= Data;
      end

      always @(posedge WrClock or posedge WPReset)
      begin
        if (WPReset)
          {wq2_rptr,wq1_rptr} <= 0;
        else
          {wq2_rptr,wq1_rptr} <= {wq1_rptr,rptr};
      end

      always @(posedge RdClock or posedge RPReset)
      begin
        if (RPReset)
          {rq2_wptr,rq1_wptr} <= 0;
        else
          {rq2_wptr,rq1_wptr} <= {rq1_wptr,wptr};
      end

      always @(posedge RdClock or posedge RPReset)
      begin
        if (RPReset)
          {rbin, rptr} <= 0;
        else
          {rbin, rptr} <= {rbinnext, rgraynext};
      end

      assign raddr      = rbin[ASIZE-1:0];
      assign rbinnext   = rbin + (RdEn & ~Empty);
      assign rgraynext  = (rbinnext>>1) ^ rbinnext;
      assign rempty_val = (rgraynext == rq2_wptr);

      assign wcount_r   = gry2bin(rq2_wptr);
      assign rcnt_sub   = {(wcount_r[ASIZE] ^ rbinnext[ASIZE]), wcount_r[ASIZE-1:0]} - {1'b0, rbinnext[ASIZE-1:0]};
      assign arempty_val= rcnt_sub <= AEMPT;

      always @(posedge RdClock or posedge RPReset)
      begin
        if (RPReset)
            RdDataNum <= 0;
        else
            RdDataNum <= rcnt_sub;
      end
      always @(posedge RdClock or posedge RPReset)
      begin
      if (RPReset)
        Empty <= 1'b1;
      else
        Empty <= rempty_val;
      end

      always @(posedge RdClock or posedge RPReset)
      begin
      if (RPReset)
        AlmostEmpty <= 1'b1;
      else
        AlmostEmpty <= arempty_val;
      end
 
      always @(posedge WrClock or posedge WPReset)
      begin
        if (WPReset)
          {wbin, wptr} <= 0;
        else
          {wbin, wptr} <= {wbinnext, wgraynext};
      end
   
      assign waddr      = wbin[ASIZE-1:0];
      assign wbinnext   = wbin + (WrEn & ~Full);
      assign wgraynext  = (wbinnext>>1) ^ wbinnext;
      assign wfull_val  = (wgraynext == {~wq2_rptr[ASIZE:ASIZE-1],
                                          wq2_rptr[ASIZE-2:0]});
  
      assign rcount_w   = gry2bin(wq2_rptr);
      assign wcnt_sub   = {(rcount_w[ASIZE] ^ wbinnext[ASIZE]), wbinnext[ASIZE-1:0]} - {1'b0, rcount_w[ASIZE-1:0]};
      assign awfull_val = wcnt_sub >= AFULL;

      always @(posedge WrClock or posedge WPReset)
      begin
        if (WPReset)
            WrDataNum <= 0;
        else
            WrDataNum <= wcnt_sub;
      end
      always @(posedge WrClock or posedge WPReset)
      begin
        if (WPReset)
          Full <= 1'b0;
        else
          Full <= wfull_val;
      end

      always @(posedge WrClock or posedge WPReset)
      begin
        if (WPReset)
          AlmostFull <= 1'b0;
        else
          AlmostFull <= awfull_val;
      end

      function [ASIZE:0]gry2bin;
        input [ASIZE:0] gry_code;
        integer         i;
        begin
          gry2bin[ASIZE]=gry_code[ASIZE];    
          for(i=ASIZE-1;i>=0;i=i-1)        
            gry2bin[i]=gry2bin[i+1]^gry_code[i];
        end
      endfunction

endmodule

`ifdef MSIM
module elastic_buffer
`else
module `getname(elastic_buffer,`module_name)
`endif
(
input	wire			clkin,
input	wire			resetn,

input   wire    [4:0]   tx_fifo_used,
input	wire		    raw_valid,
input	wire	[3:0]	raw_datak,
input	wire	[31:0]	raw_data,

output	wire	[3:0]	proc_datak,
output	wire	[31:0]	proc_data,
output	wire			proc_active

);

	reg		[31:0]	coll_data ;
	reg		[3:0]	coll_datak;   

	reg				coll_active; 
	reg		[1:0]	coll_valid;

	reg [3:0] skip ;
	reg [3:0] raw_datak_d ; 
	reg [31:0] raw_data_d ;

    reg     [15:0]  skp_cnt = 0;
	always @ ( posedge clkin ) begin
        if(tx_fifo_used >= 10) begin
            skip	<= {	(raw_data[31:24] == 8'h3C) & raw_datak[3], (raw_data[23:16] == 8'h3C) & raw_datak[2], 
                            (raw_data[15:8] == 8'h3C) & raw_datak[1],  (raw_data[7:0] == 8'h3C) & raw_datak[0] };	
            skp_cnt <= skp_cnt + 1'b1;
        end
        else begin
            skip	<= 0;	
        end
		raw_datak_d <= raw_datak ;
		raw_data_d <= raw_data ;
	end	

	reg		[31:0]	skr_data;
	reg		[3:0]	skr_datak; 
	reg		[2:0]	skr_num; 
	reg		        skr_valid;

	reg		[5:0]	acc_status;
	reg		[63:0]	acc_data;
	reg		[7:0]	acc_datak; 
	
	reg		[2:0]	acc_depth; 


assign proc_datak = coll_datak;
assign proc_data = coll_data;
assign proc_active = coll_active;

always @(posedge clkin) begin
	
	if(skr_valid)
	begin
	case(skip)
	4'b0000: begin
		skr_data 	<= raw_data_d;
		skr_datak	<= raw_datak_d; end
	4'b0001: begin
		skr_data 	<= raw_data_d[31:8];
		skr_datak	<= raw_datak_d[3:1]; end
	4'b0010: begin
		skr_data 	<= {raw_data_d[31:16], raw_data_d[7:0]};
		skr_datak	<= {raw_datak_d[3:2], raw_datak_d[0]}; end
	4'b0011: begin
		skr_data 	<= raw_data_d[31:16];
		skr_datak	<= raw_datak_d[3:2]; end
	4'b0100: begin
		skr_data 	<= {raw_data_d[31:24], raw_data_d[15:0]};
		skr_datak	<= {raw_datak_d[3], raw_datak_d[1:0]}; end
	4'b0110: begin
		skr_data 	<= {raw_data_d[31:24], raw_data_d[7:0]};
		skr_datak	<= {raw_datak_d[3], raw_datak_d[0]}; end
	4'b0111: begin
		skr_data 	<= raw_data_d[31:24];
		skr_datak	<= raw_datak_d[3]; end
	4'b1110: begin
		skr_data 	<= raw_data_d[7:0];
		skr_datak	<= raw_datak_d[0]; end
	4'b1100: begin
		skr_data 	<= raw_data_d[15:0];
		skr_datak	<= raw_datak_d[1:0]; end
	4'b1000: begin
		skr_data 	<= raw_data_d[23:0];
		skr_datak	<= raw_datak_d[2:0]; end
	4'b1111: begin
		skr_data 	<= 0;
		skr_datak	<= 0; end
	default: begin
		//{skr_status, skr_data, skr_datak} <= 0;
		{skr_data, skr_datak} <= 0;
	end
	endcase

	// count valid symbols
	skr_num <= 3'h4 - (skip[3] + skip[2] + skip[1] + skip[0]);

	end
	skr_valid <= raw_valid;
	
end

	
always @(posedge clkin) begin
	if(skr_valid)
	begin
		case(skr_num)
		0: begin end
		1: begin
			acc_data  <= {acc_data[55:0], skr_data[7:0]};
			acc_datak <= {acc_datak[6:0], skr_datak[0:0]};
			acc_depth <= acc_depth + 3'd1;
		end
		2: begin
			acc_data  <= {acc_data[47:0], skr_data[15:0]};
			acc_datak <= {acc_datak[5:0], skr_datak[1:0]};
			acc_depth <= acc_depth + 3'd2;
		end
		3: begin
			acc_data  <= {acc_data[39:0], skr_data[23:0]};
			acc_datak <= {acc_datak[4:0], skr_datak[2:0]};
			acc_depth <= acc_depth + 3'd3;
		end
		4: begin
			acc_data  <= {acc_data[31:0], skr_data[31:0]};
			acc_datak <= {acc_datak[3:0], skr_datak[3:0]};
			acc_depth <= acc_depth + 3'd4;
		end
		endcase
	
		// pick off 32bits and decrement the accumulator
		coll_valid <= skr_valid;
		coll_active <= (acc_depth > 3);
		case(acc_depth)
		4: begin
			{coll_data, coll_datak} <= {acc_data[31:0], acc_datak[3:0]};
			acc_depth <= 3'd0 + skr_num;
		end
		5: begin
			{coll_data, coll_datak} <= {acc_data[39:8], acc_datak[4:1]};
			acc_depth <= 3'd1 + skr_num;
		end
		6: begin
			{coll_data, coll_datak} <= {acc_data[47:16], acc_datak[5:2]};
			acc_depth <= 3'd2 + skr_num;
		end
		7: begin
			{coll_data, coll_datak} <= {acc_data[55:24], acc_datak[6:3]};
			acc_depth <= 3'd3 + skr_num;
		end
		endcase
	end
	else
	begin
		coll_active <= 1'b0;
	end
	
	if(~resetn) begin
		acc_depth <= 0;
	end
end

endmodule
