import React, { Component } from 'react'
import {Link, Route, Switch, withRouter} from 'react-router-dom'
import Calls from './Calls'

class _App extends Component {
  render () {
    return (
      <div>

        <div key="navbar" className="fixed-top">
          <nav className="navbar navbar-expand-md navbar-light bg-light">
            <div className="container">
              <Link to="/" className="navbar-brand">Mithra</Link>
              <div className="collapse navbar-collapse">
                <ul className="navbar-nav mr-auto">
                  <li className="nav-item">
                    <Link to="/companies" className="nav-link">
                      <i className="fa fa-bolt mr-1" aria-hidden="true"/>
                      Companies
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
          </nav>
          {/*<StatusBar app_state={this.state}/>*/}
        </div>
        <main key="main" className="container">
          <div className="content">
            <Switch>
              <Route exact path="/" render={props => (
                <Calls history={props.history}/>
              )}/>
            </Switch>
          </div>
        </main>
      </div>
    )
  }
}

export default withRouter(_App)
