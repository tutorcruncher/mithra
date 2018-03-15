import React, {Component} from 'react'

class StatusBar extends Component {
  // constructor (props) {
  //   super(props)
  // }

  // componentDidUpdate () {
  //   if (!this.state.editing && this.state.nav_title !== this.props.app_state.nav_title) {
  //     this.setState({nav_title: this.props.app_state.nav_title})
  //   }
  //   if (!this.props.app_state.nav_edit_arg && this.state.editing) {
  //     this.setState({editing: false})
  //   }
  // }
  //
  // nav_title () {
  //   if (!this.props.app_state.nav_edit_arg) {
  //     return (
  //       <span>
  //         {this.props.app_state.nav_title}
  //       </span>
  //     )
  //   } else if (this.state.editing) {
  //     return (
  //       <span className="nav-title-edit">
  //         <div className="input-group">
  //           <input
  //             type="text"
  //             className="form-control"
  //             value={this.state.nav_title}
  //             onChange={e => this.setState({nav_title: e.target.value})}/>
  //
  //           <span className="input-group-btn">
  //             <button
  //               className="btn btn-primary"
  //               type="button"
  //               onClick={this.save_nav_title}>
  //               <i className="fa fa-check" aria-hidden="true"/>
  //             </button>
  //           </span>
  //           <span className="input-group-btn">
  //             <button
  //               className="btn btn-light"
  //               type="button"
  //               onClick={() => this.setState({editing: false})}>
  //               <i className="fa fa-times" aria-hidden="true"/>
  //             </button>
  //           </span>
  //         </div>
  //       </span>
  //     )
  //   } else {
  //     return (
  //       <span>
  //         {this.props.app_state.nav_title}
  //         <i className="fa fa-pencil ml-2"
  //            onClick={() => {
  //              this.setState({editing: true})
  //            }}
  //            aria-hidden="true"/>
  //       </span>
  //     )
  //   }
  // }

  render () {
    const display_status = {
      loading: 'Loading...',
      offline: 'Offline',
      online: 'Online',
    }
    return (
      <div className={`status ${this.props.status || 'anon'}`}>
        <div className="back"/>
        <div className="container d-flex justify-content-between">
          <span>
            {this.props.title}
          </span>
          <span>
            {display_status[this.props.status] || this.props.status}
          </span>
        </div>
      </div>
    )
  }
}

export default StatusBar
