import React from 'react';
import {AgGridReact, reactCellRendererFactory} from 'ag-grid-react';
import {Button} from 'react-bootstrap';
import {StrategyControl, renderLog} from '../../static/utils';

function pad(num, size) {
    var s = num+"";
    while (s.length < size) s = "0" + s;
    return s;
}

var StrategyTable = React.createClass({
    getInitialState() {
	var l = this;
	$.getJSON("/strategy/headers/" + l.props.strategy,
		  function(d) {
		      var start = [
			  {headerName: "Id",
			   field: "id"},
			  {headerName: "Status",
			   volatile: true,
			   field: "status"},
			  {headerName: "Comment",
			   volatile: true,
			   field: "comment"},
			  {headerName: "Instrument",
			   field: "dataname",
			   editable: true,
			   defaultData: ''}
		      ];
		      var end = [
			  {headerName: "Log",
			   field: "log",
			   cellRenderer: renderLog},
			  {headerName: "Actions",
			   field: "start",
			   volatile: true,
			   cellRenderer:
			   reactCellRendererFactory(StrategyControl)
			  }];
		      for (var i=0; i < d.length; i++) {
			  d[i]['editable'] = true;
			  d[i]['volatile'] = true;
		      }
		      var items = start.concat(d).concat(end);
		      var defaultData = {};
		      for (var i=0; i < items.length; i++) {
			  if (items[i].defaultData != undefined) {
			      defaultData[items[i].field] =
				  items[i].defaultData;
			  }
		      }
		      defaultData['status'] = 'stopped';
		      defaultData['strategy'] = l.props.strategy;
		      l.setState({columnDefs: items,
				  defaultData: defaultData});
		      $.getJSON("/strategy/data/" + l.props.strategy,
				function(d) {
				    var counter = d.data.length;
				    l.setState({rowData: d.data,
						   counter: counter});
				    l.api.setRowData(d.data);
		      });
		  });
	return {
	    counter:0,
	    columnDefs: [],
	    rowData: [],
	    defaultData: {}
	};
    },
    // in onGridReady, store the api for later use
    componentWillReceiveProps(newprops) {
	if (newprops.info == undefined) {
	    return;
	}
	var r = this.state.rowData;
	for(var i=0; i < r.length; i++) {
	    var newr = newprops.info[r[i]['id']];
	    if (newr != undefined) {
		for (var attrname in newr){
		    r[i][attrname] = newr[attrname];
		}
	    }
	}
	this.setState({rowData: r});
	this.api.setRowData(r);
    },
    onGridReady(params) {
	this.api = params.api;
	this.columnApi = params.columnApi;
    },
    addRow() {
	var r = Object.assign({}, this.state.defaultData);
	var c = this.state.counter;
	var rows = this.state.rowData;
	c = c+1;
	r['id'] = r.strategy + "-" + pad(c, 5);
	rows.push(r);
	console.log(rows);
	this.setState({rowData: rows,
		       counter: c});
	this.api.setRowData(rows);
    },
    status() {
    },
    render() {
	return (
	    <div>
		<Button onClick={this.addRow}>New Strategy</Button>
	<AgGridReact
	    // column definitions and row data are immutable, the grid
	    // will update when these lists change
	    columnDefs={this.state.columnDefs}
	    rowData={this.state.rowData}
	    onGridReady={this.onGridReady}
		/></div>
	)
    }
});
    
module.exports.StrategyTable = StrategyTable;
